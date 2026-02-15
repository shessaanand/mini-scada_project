// ---------------- CONFIGURATION ----------------
const int PIN_POTENTIOMETER = A0;  // Potentiometer Wiper
const int PIN_BUTTON        = 2;   // Physical Push Button

// ---------------- STATE VARIABLES ----------------
bool systemEnabled = true;        // Logic state: true=RUN, false=STOP
int lastButtonState = HIGH;       // Previous reading (HIGH because of INPUT_PULLUP)
unsigned long lastTime = 0;       // Timer for non-blocking delays

void setup() {
  Serial.begin(9600);
  
  // INPUT_PULLUP allows connecting a button between Pin 2 and GND without a resistor
  pinMode(PIN_BUTTON, INPUT_PULLUP); 
  
  // Optional: Send a ready message
  Serial.println("SYSTEM READY");
  delay(500); 
}

void loop() {
  // ---------------------------------------------------------
  // 1. LISTEN FOR PYTHON COMMANDS
  // ---------------------------------------------------------
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == '0') {
      systemEnabled = false; // Remote STOP
    } 
    else if (cmd == '1') {
      systemEnabled = true;  // Remote START
    }
  }

  // ---------------------------------------------------------
  // 2. HANDLE PHYSICAL BUTTON (Local Toggle)
  // ---------------------------------------------------------
  int currentButtonState = digitalRead(PIN_BUTTON);
  
  // Detect Falling Edge (Transition from HIGH to LOW)
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    systemEnabled = !systemEnabled; // Toggle State
    delay(300); // Simple Debounce to prevent double clicks
  }
  
  lastButtonState = currentButtonState;

  // ---------------------------------------------------------
  // 3. SEND TELEMETRY TO PYTHON (Every 250ms)
  // ---------------------------------------------------------
  if (millis() - lastTime >= 250) { 
    lastTime = millis();
    
    // Read Potentiometer (0-1023)
    int sensorValue = analogRead(PIN_POTENTIOMETER);
    
    // Map 0-1023 to 0-100.0 degrees Celsius (Preserving 1 decimal place)
    float temperature = map(sensorValue, 0, 1023, 0, 1000) / 10.0;

    int statusFlag = systemEnabled ? 1 : 0;

    // Protocol: "0, Temperature, StatusFlag"
    Serial.print("0,");
    Serial.print(temperature);
    Serial.print(",");
    Serial.println(statusFlag);
  }
  if (lastButtonState==HIGH && currentButtonState==LOW){
    systemEnabled=!systemEnabled; //Toggle State
  }
}
