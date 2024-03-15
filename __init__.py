from datetime import datetime, timedelta

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_utils.time import to_local
from ovos_utils.time import now_local
from ovos_utils.time import to_system
from alsaaudio import Mixer


__author__ = 'BreziCode'


class QuietHours(OVOSSkill):

    ON_EVENT_NAME = 'quiet_hours_on'
    OFF_EVENT_NAME = 'quiet_hours_off'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log.debug("Executing __init__")
        self.init_settings()
        self._get_mixer()

    def _get_mixer(self):
        self.log.debug("Executing _get_mixer")
        try:
            self.mixer = Mixer()
        except Exception:
            # Retry instanciating the mixer
            try:
                self.mixer = Mixer()
            except Exception as e:
                self.log.error('Couldn\'t allocate mixer, {}'.format(repr(e)))
                self.mixer = None
        if (self.mixer is not None):
            self.saved_volume = self.mixer.getvolume()

    def initialize(self):
        self.log.debug("Executing initialize")
        self.start_time = None
        self.end_time = None
        self.detailed_message_cnt = 5
        self.saved_volume = None

        self.settings_change_callback = self._init
        self.add_event('private.mycroftai.quiet_hours', self.on_quiet_hours)

        self._init()

    def _init(self):
        self.log.debug("Executing _init")
        self.clear_events()
        if (self.settings.get('enabled')):
            self.log.info("Quiet hours skill is ENABLED")
            self.log.debug("Quiet hours mode is: {}".format(
                self.settings.get('active')))
            self.log.debug("Saved volume is: {}".format(self.saved_volume))
            self.set_start_end()
            self.set_events()
            if (self.should_turn_on_now()):
                self.log.debug('Init: truning on because enabled and should')
                self.on()
            elif (self.settings.get('active')):
                self.log.debug(
                    'Init: turning off because enabled BUT should not')
                self.off()
        else:
            self.log.info("Quiet hours skill is DISABLED")
            if (self.settings.get('active')):
                self.log.debug('Init: turning off because not enabled')
                self.off()

    def shutdown(self):
        self.log.debug("Executing shutdown")
        self.clear_events()
        self.mixer = None

    def init_settings(self):
        """Add any missing default settings."""

        self.log.debug("Executing init_settings")

        self.settings.setdefault('enabled', False)
        self.settings.setdefault('start_time_hour', 22)
        self.settings.setdefault('start_time_min', 0)
        self.settings.setdefault('end_time_hour', 8)
        self.settings.setdefault('end_time_min', 0)
        self.settings.setdefault('use_naptime', True)
        self.settings.setdefault('set_volume_to', 0)

        if (self.settings.get('set_volume_to') < 0):
            self.settings['set_volume_to'] = 0
        elif (self.settings.get('set_volume_to') > 100):
            self.settings['set_volume_to'] = 100
        self.settings.setdefault('active', False)

    def on_quiet_hours(self, message):
        self.bus.emit(
            message.response(
                data={"quiet_hours_on": self.settings.get('active')}))

    def set_start_end(self):
        """ Construct dattime objects from settings for start time and end time """
        self.log.debug("Executing set_start_end")
        now = to_local(datetime.now())
        self.start_time = now.replace(
            hour=int(self.settings.get('start_time_hour')),
            minute=int(self.settings.get('start_time_min')))
        if (self.start_time <= now):
            self.start_time += timedelta(days=1)
        self.log.debug("Start time is: {}".format(
            self.start_time.strftime("%H:%M")))
        self.end_time = now.replace(
            hour=int(self.settings.get('end_time_hour')),
            minute=int(self.settings.get('end_time_min')))
        if (self.end_time <= now):
            self.end_time += timedelta(days=1)
        self.log.debug("End time is: {}".format(
            self.end_time.strftime("%H:%M")))

    def on(self, speak=True):
        self.log.debug("Executing ON")
        if (not self.settings.get('enabled') or self.mixer is None):
            return
        self.saved_volume = self.mixer.getvolume()
        self.log.debug("Quiet hours are in efect")
        self.settings['active'] = True
        if (speak):
            self.speak_dialog('on', wait=True)
            if (self.detailed_message_cnt > 0):
                self.detailed_message_cnt = self.detailed_message_cnt - 1
                self.speak_dialog('wake.word', wait=True)
        self._set_volume(self.settings.get('set_volume_to'))

    def off(self, speak=True):
        self.log.debug("Executing OFF")
        if (not self.settings.get('enabled') or self.mixer is None):
            return
        self._set_volume(self.saved_volume[0])
        self.log.debug("Quiet hours not in effect anymore")
        self.settings['active'] = False
        if (speak):
            self.speak_dialog('off')

    def should_turn_on_now(self):
        """ Check if current time is inside teh quiet hours interval"""
        self.log.debug("Executing should_turn_on_now")
        now = now_local()
        self.log.debug("Curent time is {}".format(now.strftime("%H:%M")))
        if (self.start_time <= self.end_time):
            return (self.start_time <= now and now < self.end_time)
        else:
            return (now > self.start_time or now < self.end_time)

    def clear_events(self):
        self.log.debug("Executing clear_events")
        self.cancel_scheduled_event(self.ON_EVENT_NAME)
        self.cancel_scheduled_event(self.OFF_EVENT_NAME)

    def set_events(self):
        self.log.debug('Executing set_events')
        self.schedule_repeating_event(self.on,
                                      to_system(self.start_time),
                                      86400,
                                      name=self.ON_EVENT_NAME)
        self.schedule_repeating_event(self.off,
                                      to_system(self.end_time),
                                      86400,
                                      name=self.OFF_EVENT_NAME)

    def _set_volume(self, volume):
        self.log.debug("Executing _setvolume")
        if (self.mixer is None):
            self._get_mixer
        if (self.mixer is not None):
            self.mixer.setvolume(volume)
            self.log.debug("Volume set to {}".format(volume))
        else:
            self.log.warning("Could not set volume! Could not get mixer!")

    @intent_handler('enable.intent')
    def handle_enable_quiet_hours(self, message):
        if (self.settings.get('enabled')):
            self.speak_dialog('already.enabled')
            return
        self.settings['enabled'] = True
        self.speak_dialog('now.enabled')
        self._init()

    @intent_handler('disable.intent')
    def handle_disable_quiet_hours(self, message):
        if (not self.settings.get('enabled')):
            self.speak_dialog('already.disabled')
            return
        self.settings['enabled'] = False
        self.speak_dialog('now.disabled')
        self._init()

    @intent_handler('on.intent')
    def handle_activate_quiet_hours(self, message):
        if (not self.settings.get('enabled')):
            self.speak_dialog('disabled')
            return
        self.on()

    @intent_handler('off.intent')
    def handle_deactivate_quiet_hours(self, message):
        if (not self.settings.get('enabled')):
            self.speak_dialog('disabled')
            return
        self.off()
