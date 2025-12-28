========================================================================================================================
Mini SCADA System Prototype
========================================================================================================================
------------------------------------------------------------------------------------------------------------------------
1. Project Overview
------------------------------------------------------------------------------------------------------------------------
The Mini SCADA System is a robust Supervisory Control and Data Acquisition interface designed to simulate and monitor the operational parameters of an industrial cooling fan.

The system utilizes a split-architecture design:

Hardware Node (Arduino): Acts as the Remote Terminal Unit (RTU). It simulates temperature data using a potentiometer and handles local manual interventions via a physical push button.

HMI Dashboard (Python): A "Digital Twin" interface built with PyQt6. It visualizes real-time telemetry, renders a vector-based turbine animation, handles alarm logic, and logs operator events.

This project demonstrates core Industry 4.0 concepts, including real-time telemetry, remote actuation, and automated safety protocols.

------------------------------------------------------------------------------------------------------------------------
2. System Architecture
------------------------------------------------------------------------------------------------------------------------
	2.1 Hardware Layer (Arduino/ESP32)

		a. Sensor Simulation: A potentiometer connected to Analog Pin A0 mimics a thermocouple or RTD sensor. The firmware maps the analog voltage (0-5V) to a temperature range of 0.0°C to 100.0°C.

		b. Local Control: A physical push button connected to Pin 2 acts as a Local E-Stop/Reset. It uses INPUT_PULLUP logic to toggle the system state locally.

		c. Communication: Transmits telemetry packets via UART Serial (9600 Baud) in the CSV format: ID, Temperature, StatusFlag.

	2.2 Software Layer (Python)

		a. Framework: Built on PyQt6 for a responsive, event-driven GUI.
	
		b. Visualization: * Matplotlib: Renders a scrolling, real-time temperature trend chart.

		c. QPainter: Renders a high-performance, vector-based cooling fan animation that rotates based on system status.

		d. Logic Engine:

			Normal State (< 40°C): Fan runs at constant speed. Green indicators.

			Warning State (40°C - 50°C): System logs warnings. Amber indicators.

			Critical State (> 50°C): Triggers a 20-second safety countdown. If temperature remains critical, an Automatic Emergency Stop is triggered.

			E-Stop State: Fan halts immediately. Red overlay blocks UI to force operator acknowledgement.
------------------------------------------------------------------------------------------------------------------------
3. Engineering Theory: Industrial Cooling
------------------------------------------------------------------------------------------------------------------------
	3.1 The Physics of Heat Dissipation

		In industrial electronics and rotating machinery, heat is the primary cause of component degradation. As current flows through circuits (Joule heating) or friction occurs in bearings, thermal energy accumulates.

		Cooling fans function on the principle of forced convection. By increasing the velocity of air over a heat sink or motor casing, the heat transfer coefficient is significantly increased compared to natural convection, allowing the system to maintain thermal equilibrium.

	3.2 Control Strategies: This project implements a Threshold-based Control System with safety interlocks:

		a. Monitoring: Continuous sampling of the process variable (Temperature).
	
		b. Logic: Comparison against setpoints (Warning at 40°C, Critical at 50°C).

		c. Actuation: Binary control (Run/Stop) of the fan visualization based on safety states.
------------------------------------------------------------------------------------------------------------------------
4. Industrial Safety Standards & Compliance
------------------------------------------------------------------------------------------------------------------------
In a real-world industrial setting (e.g., Power Plants, Manufacturing lines), SCADA systems must adhere to strict standards to protect equipment and personnel. Two of the most critical parameters monitored are Temperature and Vibration.

	4.1 Temperature Standards (The Focus of this Project)

		a. Excessive heat causes insulation breakdown in motors (e.g., winding failure).

		b. IEC 60085: Defines thermal classes for electrical insulation.

		c. Safety Implication: If a motor exceeds its rated thermal class (e.g., Class F = 155°C), its lifespan is halved for every 10°C rise above that limit (Arrhenius equation).

		d. SCADA Role: This project mimics the "Thermal Overload Protection" found in Variable Frequency Drives (VFDs) by initiating a countdown and trip (E-Stop) when critical thresholds are breached.

	4.2 Vibration Standards (Future Context)

		a. While temperature indicates electrical or load stress, vibration indicates mechanical failure (bearing wear, misalignment, unbalance).

		b. ISO 10816: The global standard for evaluating mechanical vibration in machines. It categorizes severity based on velocity (mm/s).

		c. Safety Implication: High vibration leads to catastrophic mechanical failure (shaft shearing, casing explosion).

		d. SCADA Role: A complete monitoring system monitors both. A fan might be cool but vibrating violently due to a broken blade.
------------------------------------------------------------------------------------------------------------------------
5. Future Enhancements: Vibration Analysis
------------------------------------------------------------------------------------------------------------------------
The current iteration focuses on thermal monitoring. The planned "Phase 2" of this project involves integrating Vibration Monitoring to create a complete Condition Monitoring System (CMS).

Planned Features:

	a. Hardware Upgrade: Integration of an Accelerometer (e.g., ADXL345 or MPU6050) to the Arduino.

	b. Data Processing: calculating the RMS (Root Mean Square) velocity of the vibration.

	c. Dashboard Integration: * A secondary chart for Vibration vs. Time.

	d. Implementation of ISO 10816 Zone logic (Zone A=Good, Zone D=Danger).

	e. Combined Logic: The E-Stop will trigger if either Temperature > 50°C OR Vibration > 4.5 mm/s (Simulated).
------------------------------------------------------------------------------------------------------------------------
6. Installation & Usage
------------------------------------------------------------------------------------------------------------------------
Prerequisites:

	Python 3.9+

	Arduino IDE

Setup:

	Python: Install dependencies: pip install PyQt6 matplotlib pyserial numpy
	Arduino: 
		Upload mini_scada.ino to your microcontroller.
		Wire Potentiometer Signal to A0.
		Wire Button between Pin 2 and GND.
	Config: 
		Update PORT = "COMx" in mini_scada.py to match your Arduino.

Operation:

	Run python mini_scada.py.
	The splash screen will load.
	Turn the potentiometer to vary temperature.
	Observe the chart.
	Press the physical button or the GUI "STOP" button to test the Emergency Stop logic.
