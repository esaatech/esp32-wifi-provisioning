from setup_button import SetupButton
import time

button = SetupButton()

print("Setup Button Test")
print("----------------------------")

while True:

    if button.wait_for_long_press():

        print()
        print("ENTER SETUP MODE")
        print()

        # Wait until the button is released before
        # allowing another detection.
        while button.is_pressed():
            time.sleep_ms(50)

    time.sleep_ms(50)