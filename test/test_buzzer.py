#!/usr/bin/env python3

# passive

import RPi.GPIO as GPIO
import time

BUZZER_PIN = 12   # GPIO12

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

pwm = GPIO.PWM(BUZZER_PIN, 1000)

try:
    pwm.start(50)

    for freq in [262, 330, 392, 523, 784, 1000]:
        pwm.ChangeFrequency(freq)
        time.sleep(0.4)

finally:
    pwm.stop()
    GPIO.cleanup()