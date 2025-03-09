#include <AccelStepper.h>
#include <TMCStepper.h>

#define STEP_PIN_X 3
#define DIR_PIN_X 2
#define STEP_PIN_Y 5
#define DIR_PIN_Y 4
#define EN_PIN 8 // Enable pin for TMC2209
#define LIMIT_SWITCH_X 12
#define LIMIT_SWITCH_Y 13

#define R_SENSE 0.11f      // For TMC2209 drivers

// Stepper objects
AccelStepper stepperX(AccelStepper::DRIVER, STEP_PIN_X, DIR_PIN_X);
AccelStepper stepperY(AccelStepper::DRIVER, STEP_PIN_Y, DIR_PIN_Y);

TMC2209Stepper driverX = TMC2209Stepper(EN_PIN, DIR_PIN_X, STEP_PIN_X, R_SENSE);
TMC2209Stepper driverY = TMC2209Stepper(EN_PIN, DIR_PIN_Y, STEP_PIN_Y, R_SENSE);

void setup() {
    Serial.begin(115200); // Serial monitor for G-code input

    pinMode(EN_PIN, OUTPUT);
    digitalWrite(EN_PIN, LOW); // Enable TMC2209

    pinMode(LIMIT_SWITCH_X, INPUT_PULLUP);
    pinMode(LIMIT_SWITCH_Y, INPUT_PULLUP);

    driverX.begin();  // Initialize driver for X axis
    driverY.begin();  // Initialize driver for Y axis

    driverX.rms_current(1000); // Set current in mA (adjust as needed)
    driverY.rms_current(1000);

    stepperX.setMaxSpeed(2000); // Increase speed
    stepperX.setAcceleration(1000); // Increase acceleration
    stepperY.setMaxSpeed(2000);
    stepperY.setAcceleration(1000);

    stepperY.setPinsInverted(true, false, false);
    stepperX.setPinsInverted(true, false, false);

    Serial.println("System ready. Send 'TEST_X' or 'TEST_Y' to test motors, 'LIMIT' to check switches.");
}

void loop() {
    if (Serial.available()) {
        String input = Serial.readStringUntil('\n');
        input.trim();

        if (input == "CALIBRATE") {
            calibrateY();
            calibrateX();
        } else if (input == "TEST_X") {
            testStepper(stepperX, "X");
        } else if (input == "TEST_Y") {
            testStepper(stepperY, "Y");
        } else if (input == "LIMIT") {
            checkLimitSwitches();
        } else {
            processGCode(input);
        }
    }

    stepperX.run();
    stepperY.run();
}

void calibrateY() {
    Serial.println("Calibrating Y-axis...");
    while (digitalRead(LIMIT_SWITCH_Y) == HIGH) { // Move in positive direction until limit switch triggers
        stepperY.move(-100);
        stepperY.run();
        delay(1);
    }
    stepperY.setCurrentPosition(0); // Set current position as zero
    Serial.println("Calibration complete. Y-axis zeroed.");
}

void calibrateX() {
    Serial.println("Calibrating X-axis...");
    while (digitalRead(LIMIT_SWITCH_X) == HIGH) { // Move in positive direction until limit switch triggers
        stepperX.move(-100);
        stepperX.run();
        delay(1);
    }
    stepperX.setCurrentPosition(0); // Set current position as zero
    Serial.println("Calibration complete. X-axis zeroed.");
}


void processGCode(String gcode) {
    gcode.trim();
    if (gcode.startsWith("G1")) { // G1 for coordinated linear move
        float x = 0.0, y = 0.0, feedrate = 100.0;

        if (gcode.indexOf('X') != -1) {
            x = gcode.substring(gcode.indexOf('X') + 1).toFloat();
        }
        if (gcode.indexOf('Y') != -1) {
            y = gcode.substring(gcode.indexOf('Y') + 1).toFloat();
        }
        if (gcode.indexOf('F') != -1) {
            feedrate = gcode.substring(gcode.indexOf('F') + 1).toFloat();
        }

        stepperX.moveTo(x * 100); // Convert mm to steps (adjust scaling if needed)
        stepperY.moveTo(y * 100);
        stepperX.setSpeed(feedrate);
        stepperY.setSpeed(feedrate);
    }
}

void testStepper(AccelStepper &stepper, const char* axis) {
    Serial.print("Testing stepper motor on axis ");
    Serial.println(axis);
    for (int i = 0; i < 1000; i++) {
        stepper.move(100);
        stepper.run();
        delay(1);
    }
    for (int i = 0; i < 1000; i++) {
        stepper.move(-100);
        stepper.run();
        delay(1);
    }
    Serial.println("Test complete.");
}

void checkLimitSwitches() {
    Serial.print("Limit Switch X: ");
    Serial.println(digitalRead(LIMIT_SWITCH_X) == LOW ? "TRIGGERED" : "NOT TRIGGERED");

    Serial.print("Limit Switch Y: ");
    Serial.println(digitalRead(LIMIT_SWITCH_Y) == LOW ? "TRIGGERED" : "NOT TRIGGERED");
}