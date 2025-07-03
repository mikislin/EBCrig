import RPi.GPIO as GPIO
import time

# ——— Configuration ———
LED_PIN = 18      # BCM pin 18 (physical pin 12)
FREQUENCY = 1000  # PWM frequency in Hz

# ——— Setup ———
GPIO.setmode(GPIO.BCM)           # Use Broadcom pin numbering
GPIO.setup(LED_PIN, GPIO.OUT)    # Set LED_PIN as an output

# Create a PWM object on LED_PIN at specified frequency
pwm = GPIO.PWM(LED_PIN, FREQUENCY)

# Start PWM with 0% duty cycle (LED off)
pwm.start(0)

try:
    while True:
        # Fade LED up from 0% to 100%
        for duty in range(0, 101, 5):
            pwm.ChangeDutyCycle(duty)  # Set brightness
            time.sleep(0.05)           # Short pause (50 ms)

        # Fade LED down from 100% to 0%
        for duty in range(100, -1, -5):
            pwm.ChangeDutyCycle(duty)
            time.sleep(0.05)

except KeyboardInterrupt:
    # If CTRL+C is pressed, exit the loop
    pass

finally:
    # ——— Cleanup ———
    pwm.stop()       # Stop PWM
    GPIO.cleanup()   # Reset GPIO pins to safe state
