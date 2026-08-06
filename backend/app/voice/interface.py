"""JARVIS OS - Voice Interface"""
from abc import ABC, abstractmethod
from typing import Optional, Callable
import threading


class STTEngine(ABC):
    @abstractmethod
    def listen(self) -> Optional[str]:
        pass

    @abstractmethod
    def start_continuous(self, callback: Callable[[str], None]):
        pass

    @abstractmethod
    def stop(self):
        pass


class TTSEngine(ABC):
    @abstractmethod
    def speak(self, text: str):
        pass

    @abstractmethod
    def stop(self):
        pass


class LocalSTT(STTEngine):
    def __init__(self, wake_word: str = "jarvis"):
        import speech_recognition as sr
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.wake_word = wake_word.lower()
        self._running = False

    def listen(self) -> Optional[str]:
        import speech_recognition as sr
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio)
                return text
            except (sr.UnknownValueError, sr.WaitTimeoutError):
                return None

    def start_continuous(self, callback: Callable[[str], None]):
        self._running = True

        def _loop():
            while self._running:
                text = self.listen()
                if text and self.wake_word in text.lower():
                    # Remove wake word and pass rest
                    cleaned = text.lower().replace(self.wake_word, "").strip()
                    if cleaned:
                        callback(cleaned)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False


class LocalTTS(TTSEngine):
    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        # Try to use a male voice
        for voice in voices:
            if 'male' in voice.name.lower() or 'david' in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break
        self.engine.setProperty('rate', 175)

    def speak(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()

    def stop(self):
        self.engine.stop()


class VoiceInterface:
    """Unified voice interface managing STT and TTS."""

    def __init__(self, wake_word: str = "jarvis"):
        self.stt: Optional[STTEngine] = None
        self.tts: Optional[TTSEngine] = None
        self.wake_word = wake_word
        self._initialized = False

    def initialize(self):
        try:
            self.stt = LocalSTT(self.wake_word)
            self.tts = LocalTTS()
            self._initialized = True
        except Exception:
            self._initialized = False

    def speak(self, text: str):
        if self.tts:
            self.tts.speak(text)

    def listen(self) -> Optional[str]:
        if self.stt:
            return self.stt.listen()
        return None

    def start_wake_word_detection(self, callback: Callable[[str], None]):
        if self.stt:
            self.stt.start_continuous(callback)

    def stop(self):
        if self.stt:
            self.stt.stop()

    @property
    def is_available(self) -> bool:
        return self._initialized
