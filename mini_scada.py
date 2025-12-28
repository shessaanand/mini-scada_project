'''
PYTHON VERSION: 3.9+
DEPENDENCIES: PyQt6, Matplotlib, Pyserial, Numpy
'''
import math
import random
import sys
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Union, Any

# Third-party Scientific & Plotting Libraries
import numpy as np
import serial
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# PyQT6 Core Framework Imports
from PyQt6.QtCore import (
    Qt, 
    QTimer, 
    QPointF
)
from PyQt6.QtGui import (
    QPainter, 
    QPen, 
    QColor, 
    QPainterPath, 
    QFont, 
    QRadialGradient, 
    QPaintEvent,
    QResizeEvent,
    QMouseEvent
)
from PyQt6.QtWidgets import (
    QApplication, 
    QWidget, 
    QLabel, 
    QVBoxLayout, 
    QHBoxLayout,
    QFrame, 
    QListWidget, 
    QGridLayout, 
    QSizePolicy, 
    QListWidgetItem,
    QGraphicsDropShadowEffect, 
    QStackedLayout
)

# -----------------------------------------------------------------------------
# GLOBAL CONFIGURATION CONSTANTS
# -----------------------------------------------------------------------------

# Serial Communication Settings
PORT: str = "COM10"
"""Default serial port for hardware connection."""

BAUD_RATE: int = 9600
"""Baud rate for UART communication."""

# Application Constraints
MAX_LOG_ENTRIES: int = 50
"""Maximum number of lines retained in the event log before recycling."""

CONSTANT_FAN_SPEED: float = 10.0
"""Target angular velocity for the turbine animation in normal operation."""

# Simulation Toggle
# Set to False if connecting to actual hardware (Arduino/PLC).
# If Serial connection fails, the system will auto-fallback to simulation regardless of this flag.
USE_SIMULATION: bool = False

# Operational Safety Thresholds (Degrees Celsius)
TEMP_THRESHOLD_WARNING: float = 40.0
"""Temperature at which the system enters WARNING state (Amber)."""

TEMP_THRESHOLD_CRITICAL: float = 50.0
"""Temperature at which the system enters CRITICAL state (Red)."""

COUNTDOWN_START_SECONDS: int = 20
"""Duration of the countdown timer before automatic shutdown triggers."""


# -----------------------------------------------------------------------------
# STYLING & THEME MANAGEMENT
# -----------------------------------------------------------------------------
def get_stylesheet(card_bg_color: str = "#1e1e1e") -> str:
    """
    Generates the global CSS-like stylesheet for the Qt Application.
    
    This function creates a centralized theme definition, ensuring consistency
    across all widgets, frames, and labels.

    Args:
        card_bg_color (str): Hex color code for card backgrounds. Defaults to dark grey.
    
    Returns:
        str: The complete stylesheet string ready for `app.setStyleSheet()`.
    """
    return f"""
    /* GLOBAL WIDGET STYLING */
    QWidget {{
        background: #121212;
        color: #e0e0e0;
        font-family: 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
    }}
    
    /* MAIN HEADER TITLE - Blue Accent */
    QLabel#MainTitle {{
        background: #1565C0;
        color: white;
        font-size: 28px;
        font-weight: bold;
        padding: 12px;
        border-radius: 8px;
        border: 2px solid #0D47A1;
        margin-bottom: 5px;
    }}

    /* DASHBOARD CARDS (Panels) */
    QFrame#Card, QFrame#ControlCard, QFrame#MessageCard, QFrame#ActionCard {{
        background: {card_bg_color}; 
        border-radius: 12px;
        border: 2px solid #333;
    }}

    /* CARD HEADERS (Small Caps Titles) */
    QLabel#Title {{
        color: #ccc;
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        padding: 8px;
        background: #2c2c2c; 
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom: 1px solid #333;
    }}
    
    /* DIGITAL VALUE DISPLAYS (Large Numbers) */
    QLabel#Value {{
        font-size: 56px; 
        font-weight: bold;
        color: #fff;
        background: transparent;
    }}
    
    /* UNIT LABEL (Small suffix) */
    QLabel#Unit {{
        font-size: 18px;
        color: #888;
        padding-bottom: 12px;
    }}
    
    /* EVENT LOG LIST WIDGET */
    QListWidget {{
        background: transparent;
        border: none;
        font-family: 'Consolas', monospace;
        font-size: 11px;
        color: #aaa;
        padding: 5px;
    }}
    
    /* DIGITAL COUNTDOWN TIMER DISPLAY (Monospace) */
    QLabel#TimerDisplay {{
        font-family: 'Consolas', 'Courier New', monospace; 
        font-size: 48px; 
        font-weight: bold;
        background-color: #080808; 
        border: 2px solid #333;
        border-radius: 6px;
        padding: 4px 10px;
        margin-top: 5px;
    }}
    """


# -----------------------------------------------------------------------------
# HARDWARE ABSTRACTION LAYER (MOCK)
# -----------------------------------------------------------------------------
class MockSerial:
    """
    Simulates a serial connection interface for development and testing.
    
    This class mimics the behavior of the `pyserial` library, generating synthetic
    sine-wave temperature data to simulate realistic heating and cooling cycles
    without physical hardware.
    """
    def __init__(self) -> None:
        """Initializes the mock serial connection timer."""
        self.start_time: float = time.time()
        self.in_waiting: bool = True
        self._buffer: bytes = b""

    def read_all(self) -> bytes:
        """
        Simulates reading all available bytes from the UART buffer.
        
        The generated data follows the protocol: "ID, Temperature, StatusFlag"
        Example: "0,25.50,1"
        
        Returns:
            bytes: Encoded byte string containing the simulated telemetry data.
        """
        elapsed = time.time() - self.start_time
        
        # Physics Simulation:
        # Generate a temperature value based on a sine wave to test threshold logic.
        # Oscillates between roughly -5 and +55 degrees Celsius.
        # Adds random noise (0.0 - 0.2) to simulate sensor jitter.
        base_temp = 25
        amplitude = 30
        frequency = 0.1
        noise = random.random() * 0.2
        
        temp = base_temp + (amplitude * math.sin(elapsed * frequency)) + noise
        
        # Status flag simulation: 1 = Running, 0 = Hardware Stop (e.g. physical button pressed)
        status_flag = 1 
        
        # Construct the CSV-style packet
        data_str = f"0,{temp:.2f},{status_flag}\n"
        return data_str.encode('utf-8')
        
    def write(self, data: bytes) -> None:
        """
        Simulates writing bytes to the serial port (TX).
        
        Args:
            data (bytes): The command bytes to send (e.g., b'1' or b'0').
        """
        # In a real application, this would send commands to the PLC/Arduino.
        # For simulation, we simply pass.
        pass


# -----------------------------------------------------------------------------
# CUSTOM WIDGET: EMERGENCY OVERLAY
# -----------------------------------------------------------------------------
class EmergencyOverlay(QWidget):
    """
    A full-screen semi-transparent overlay widget that alerts the user to Critical States.
    
    This widget sits on top of the dashboard and blocks interaction with underlying
    elements (except for itself), forcing the user to acknowledge the emergency
    condition before resetting the system.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the overlay widget.

        Args:
            parent (QWidget, optional): The parent widget (usually the Main Window).
        """
        super().__init__(parent)
        
        # Important: By setting WA_TransparentForMouseEvents to False, we ensure
        # this widget captures all mouse clicks, effectively 'modalizing' the UI
        # beneath it without opening a new window.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False) 
        self.setVisible(False)
        
        # Use a Vertical Layout to center the warning message
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Main Warning Text
        self.lbl_warning = QLabel("!!! EMERGENCY STOP ACTIVE !!!")
        self.lbl_warning.setStyleSheet("""
            color: white; 
            font-size: 48px; 
            font-weight: bold; 
            background: transparent;
            border: 4px solid white;
            padding: 20px;
            border-radius: 10px;
        """)
        self.lbl_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 2. Sub-instruction Text
        self.lbl_sub = QLabel("CLICK ANYWHERE TO \nACKNOWLEDGE AND ACCESS \nRESET CONTROLS")
        self.lbl_sub.setStyleSheet("color: white; font-size: 24px; margin-top: 10px; font-weight: bold;")
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 3. Visual Polish: Drop Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        self.lbl_warning.setGraphicsEffect(shadow)

        layout.addWidget(self.lbl_warning)
        layout.addWidget(self.lbl_sub)
    
    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Custom paint handler to render the dimming effect.
        
        We draw a semi-transparent red rectangle over the entire widget area
        to visually indicate a 'halted' or 'danger' state.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill rect with Red (R=150, G=0, B=0) and Alpha=180 (Semi-transparent)
        painter.fillRect(self.rect(), QColor(150, 0, 0, 180))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse clicks.
        
        Clicking anywhere on the overlay acknowledges the warning and hides
        the overlay, allowing the user to click the actual 'RESET' button underneath.
        """
        self.setVisible(False)


# -----------------------------------------------------------------------------
# CUSTOM WIDGET: INTEGRATED SPLASH SCREEN
# -----------------------------------------------------------------------------
class IntegratedSplashScreen(QWidget):
    """
    A stylized loading screen widget designed to be embedded in a QStackedLayout.
    
    This acts as the first 'page' of the application, showing branding and
    simulated initialization status before transitioning to the main dashboard.
    """
    def __init__(self) -> None:
        super().__init__()
        
        # Main layout centers everything
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Container frame for the visual card
        bg_frame = QFrame()
        bg_frame.setObjectName("SplashFrame")
        bg_frame.setFixedSize(600, 350)
        
        inner_layout = QVBoxLayout(bg_frame)
        inner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.setSpacing(20)
        
        # 1. Branding Title
        lbl_brand = QLabel("MiniSCADA")
        lbl_brand.setObjectName("SplashTitle")
        lbl_brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 2. Tagline
        lbl_tagline = QLabel("SYSTEM INITIALIZATION...")
        lbl_tagline.setObjectName("SplashTagline")
        lbl_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 3. Loading Bar Simulation
        lbl_loading = QLabel("Loading Modules: [||||||||||] 100%")
        lbl_loading.setObjectName("SplashLoader")
        lbl_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner_layout.addStretch()
        inner_layout.addWidget(lbl_brand)
        inner_layout.addWidget(lbl_tagline)
        inner_layout.addSpacing(30)
        inner_layout.addWidget(lbl_loading)
        inner_layout.addStretch()
        
        main_layout.addWidget(bg_frame)
        
        # Local styling for Splash elements
        self.setStyleSheet("""
            QFrame#SplashFrame {
                background-color: #121212; 
                border: 2px solid #333;
                border-radius: 12px;
            }
            QLabel#SplashTitle {
                background: #1565C0;
                color: white;
                font-family: 'Segoe UI', sans-serif;
                font-size: 42px;
                font-weight: bold;
                padding: 15px 40px;
                border-radius: 8px;
                border: 2px solid #0D47A1;
            }
            QLabel#SplashTagline {
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 18px;
                font-weight: 300;
                letter-spacing: 2px;
                text-transform: uppercase;
            }
            QLabel#SplashLoader {
                color: #00E676;
                font-family: 'Consolas', monospace;
                font-size: 14px;
            }
        """)


# -----------------------------------------------------------------------------
# CUSTOM WIDGET: EMERGENCY STOP BUTTON
# -----------------------------------------------------------------------------
class EmergencyStopButton(QWidget):
    """
    A custom-drawn circular button representing a physical industrial E-Stop switch.
    
    This widget does not use standard QPushButtons but renders its own state
    using QPainter to achieve a realistic 'big red button' look.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active: bool = False
        self.callback: Optional[callable] = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handles click events to toggle the stop state."""
        self.is_active = not self.is_active
        self.update() # Trigger a repaint to show new color/text
        
        if self.callback:
            self.callback(self.is_active)

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Renders the button graphics.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        
        # 1. Draw Outer Housing (Dark Red Base)
        painter.setBrush(QColor("#800000"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)
        
        # 2. Draw Inner Active Button
        # Logic: If active (Stopped), use darker red. If inactive (Run), use bright red.
        inner_rect = rect.adjusted(5, 5, -5, -5)
        color = QColor("#D32F2F") if self.is_active else QColor("#FF5252")
        
        painter.setBrush(color)
        painter.setPen(QPen(QColor("black"), 2))
        painter.drawEllipse(inner_rect)
        
        # 3. Draw Text Label
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        text = "RESET" if self.is_active else "STOP"
        painter.drawText(inner_rect, Qt.AlignmentFlag.AlignCenter, text)


# -----------------------------------------------------------------------------
# CUSTOM WIDGET: TREND CHART CANVAS
# -----------------------------------------------------------------------------
class TrendChart(FigureCanvasQTAgg):
    """
    A Matplotlib canvas integrated into PyQT6 for rendering real-time data trends.
    
    Configured with a dark theme to match the application aesthetic.
    """
    def __init__(self) -> None:
        # Create a Figure with specific aspect ratio and DPI
        self.fig = Figure(figsize=(5, 2), dpi=90)
        self.fig.patch.set_facecolor('#1e1e1e') # Dark background for figure
        
        # Add a subplot
        self.ax = self.fig.add_subplot(111)
        
        # Make the plot area transparent so it blends with the widget background
        self.fig.patch.set_alpha(0)
        self.ax.patch.set_alpha(0)
        
        # Style the Axes (White text, invisible top/right spines)
        self.ax.tick_params(colors='#fff', labelsize=8)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_color('#888')
        self.ax.spines['left'].set_color('#888')
        
        # Add grid lines for readability
        self.ax.grid(True, color='#555', ls='--', lw=0.5)
        
        # Tight layout adjustment manually
        self.fig.subplots_adjust(left=0.12, right=0.95, top=0.9, bottom=0.2)
        
        super().__init__(self.fig)


# -----------------------------------------------------------------------------
# CUSTOM WIDGET: ANIMATED TURBINE
# -----------------------------------------------------------------------------
class TurbineWidget(QWidget):
    """
    A vector-graphics based widget simulating a cooling fan or turbine.
    
    This widget is optimized for 60FPS animation, using QPainterPath to define
    complex blade geometry once and rotating the coordinate system during paint events.
    """
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(220, 220)
        
        # Animation State
        self.angle: float = 0
        self.color: QColor = QColor("#FFC107")
        
        # Pre-calculate the blade shape path to save CPU cycles during paintEvent
        self.blade_path = QPainterPath()
        self.blade_path.moveTo(0, 15) 
        self.blade_path.cubicTo(10, 40, 20, 70, 45, 95) 
        self.blade_path.lineTo(60, 90)
        self.blade_path.cubicTo(35, 60, 25, 30, 10, 15)
        self.blade_path.closeSubpath()

    def update_state(self, angle: float, color: QColor) -> None:
        """
        Updates the rotation angle and color of the turbine.
        Triggers a repaint only if values have changed.

        Args:
            angle (float): The current rotation angle in degrees (0-360).
            color (QColor): The color of the blades (indicates status).
        """
        if self.angle != angle or self.color != color:
            self.angle = angle
            self.color = color
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Renders the turbine geometry.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        center = QPointF(w / 2, h / 2)
        radius = min(w, h) / 2 - 10
        scale_factor = radius / 100.0

        # 1. Draw Static Housing Ring
        painter.setPen(QPen(QColor("#333"), 6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)
        
        # 2. Draw Static Crossbars
        painter.setPen(QPen(QColor("#2a2a2a"), 4))
        painter.drawLine(QPointF(center.x() - radius, center.y()), QPointF(center.x() + radius, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - radius), QPointF(center.x(), center.y() + radius))

        # 3. Draw Rotating Blades
        # We save the painter state, translate to center, rotate, scale, draw, and restore.
        painter.setPen(QPen(QColor("#111"), 1)) 
        painter.setBrush(self.color)
        
        num_blades = 5
        for i in range(num_blades):
            painter.save()
            painter.translate(center)
            # Offset rotation by i * (360 / num_blades) to space blades evenly
            painter.rotate(self.angle + (i * (360 / num_blades)))
            painter.scale(scale_factor, scale_factor)
            painter.drawPath(self.blade_path)
            painter.restore()

        # 4. Draw Center Hub (with Gradient)
        gradient = QRadialGradient(center, 25 * scale_factor)
        gradient.setColorAt(0, QColor("#444"))
        gradient.setColorAt(1, QColor("#111"))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, 25 * scale_factor, 25 * scale_factor)
        
        # 5. Draw Center Bolt
        painter.setBrush(QColor("#666"))
        painter.drawEllipse(center, 5 * scale_factor, 5 * scale_factor)
        painter.end()


# -----------------------------------------------------------------------------
# MAIN APPLICATION CONTROLLER
# -----------------------------------------------------------------------------
class ScadaDashboard(QWidget):
    """
    The main application controller class.
    
    Responsibilities:
    1.  UI Construction & Layout Management (Splash -> Dashboard).
    2.  State Management (Temperature, E-Stop, Alarms).
    3.  Timer Management (Animation Loop, Data Polling, Logic Tick).
    4.  Event Handling (User Input, Serial Data).
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MiniSCADA v7.0")
        self.resize(1000, 700)
        
        # Apply Global Styling
        self.setStyleSheet(get_stylesheet("#1e1e1e"))
        
        # ---------------------------------------------------------
        # INITIALIZE STATE VARIABLES
        # ---------------------------------------------------------
        self.current_temp: float = 0.0
        self.turbine_angle: float = 0.0
        
        self.system_status: str = ""
        self.is_estopped: bool = False      # Software E-Stop state
        self.is_hard_paused: bool = False   # Hardware button state
        
        self.runtime_seconds: int = 0
        self.countdown_val: int = COUNTDOWN_START_SECONDS
        self.is_countdown_active: bool = False
        
        # Data Buffers for Charting (Numpy for performance)
        self.data_x: np.ndarray = np.arange(50)
        self.data_y: np.ndarray = np.zeros(50)
        
        self.legend_items: Dict[str, Dict[str, Any]] = {}
        self.current_severity: str = "normal" 

        # ---------------------------------------------------------
        # SETUP VIEW ARCHITECTURE (STACKED LAYOUT)
        # ---------------------------------------------------------
        # We use a QStackedLayout to manage the transition from the
        # Splash Screen to the Main Dashboard without opening new windows.
        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        
        # Index 0: Splash Screen
        self.splash_view = IntegratedSplashScreen()
        self.stacked_layout.addWidget(self.splash_view)
        
        # Index 1: Dashboard Container
        self.dashboard_view = QWidget()
        self.stacked_layout.addWidget(self.dashboard_view)
        
        # Build the UI inside the dashboard container
        self.setup_dashboard_ui(self.dashboard_view)
        
        # Initialize Overlay (Parented to self so it covers EVERYTHING)
        self.overlay = EmergencyOverlay(self)
        self.overlay.resize(self.size())
        
        # ---------------------------------------------------------
        # STARTUP SEQUENCE
        # ---------------------------------------------------------
        # Start showing the splash screen
        self.stacked_layout.setCurrentIndex(0)
        
        # Schedule the transition to the main dashboard after 3 seconds
        QTimer.singleShot(3000, self.transition_to_dashboard)

    def transition_to_dashboard(self) -> None:
        """
        Callback fired when splash screen timer expires.
        Switches the visible view to the dashboard and kicks off system logic.
        """
        self.stacked_layout.setCurrentIndex(1)
        self.start_system_logic()

    def start_system_logic(self) -> None:
        """
        Initializes the core system loops.
        This is deferred until AFTER the splash screen to improve perceived startup performance.
        """
        # 1. Establish Serial Connection
        self.setup_serial()

        # 2. Start Animation Timer (High Frequency ~60 FPS)
        # Handles smooth turbine rotation and chart redrawing.
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(16) # ~16ms = 60 FPS

        # 3. Start Data Polling Timer (Medium Frequency 10Hz)
        # Handles reading from the serial buffer.
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.read_serial_data)
        self.data_timer.start(100) # 100ms

        # 4. Start Logic Timer (Low Frequency 1Hz)
        # Handles runtime counters, countdown timers, and logging.
        self.runtime_timer = QTimer()
        self.runtime_timer.timeout.connect(self.update_seconds_logic)
        self.runtime_timer.start(1000) # 1000ms = 1s
        
        self.log_event("SYS: Dashboard Initialized & Loops Started")
        self.refresh_legend()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle window resize events.
        Ensures the overlay always covers the full window dimensions.
        """
        self.overlay.resize(self.size())
        super().resizeEvent(event)

    def setup_dashboard_ui(self, container_widget: QWidget) -> None:
        """
        Constructs the complex grid layout of the dashboard.
        
        Args:
            container_widget (QWidget): The widget acting as the holder for the dashboard.
        """
        main_layout = QVBoxLayout(container_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. HEADER SECTION
        self.lbl_main_title = QLabel("MINI SCADA SYSTEM MONITOR")
        self.lbl_main_title.setObjectName("MainTitle")
        self.lbl_main_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_main_title)

        # 2. CONTENT AREA (Horizontal Split)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # --- LEFT COLUMN: EVENT LOG ---
        col_left = QVBoxLayout()
        self.frame_log = QFrame(objectName="Card")
        layout_log = QVBoxLayout(self.frame_log)
        layout_log.setContentsMargins(0,0,0,10)
        layout_log.setSpacing(5)
        
        lbl_log_title = QLabel("EVENT LOG", objectName="Title")
        lbl_log_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_log.addWidget(lbl_log_title)
        
        self.log_widget = QListWidget()
        layout_log.addWidget(self.log_widget)
        col_left.addWidget(self.frame_log)
        content_layout.addLayout(col_left, stretch=20)

        # --- CENTER COLUMN: MAIN CONTROLS & CHARTS ---
        col_center = QVBoxLayout()
        col_center.setSpacing(20)

        # A. Status Banner
        frame_alarm = QFrame(objectName="Card")
        frame_alarm.setFixedHeight(65)
        layout_alarm = QVBoxLayout(frame_alarm)
        layout_alarm.setContentsMargins(5,5,5,5)
        self.lbl_alarm_banner = QLabel("SYSTEM READY")
        self.lbl_alarm_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_alarm_banner.setStyleSheet("background: #00E676; color: #000; font-weight: bold; border-radius: 4px; font-size: 18px;")
        layout_alarm.addWidget(self.lbl_alarm_banner)
        col_center.addWidget(frame_alarm)

        # B. Operator Message Board
        self.frame_msg = QFrame(objectName="MessageCard")
        layout_msg = QVBoxLayout(self.frame_msg)
        layout_msg.setContentsMargins(0,0,0,10)
        
        self.lbl_msg_title = QLabel("OPERATOR'S MESSAGE", objectName="Title")
        self.lbl_msg_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_msg_text = QLabel("TEMPERATURE LEVELS SAFE...\nMONITORING ACTIVE.")
        self.lbl_msg_text.setStyleSheet("color: #888; font-size: 24px; font-style: italic;")
        self.lbl_msg_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_msg_text.setWordWrap(True)
        
        # Countdown Timer (Hidden by default)
        self.lbl_countdown = QLabel("00:00:20")
        self.lbl_countdown.setObjectName("TimerDisplay") 
        self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_countdown.setStyleSheet("color: #00E676;")
        
        layout_msg.addWidget(self.lbl_msg_title)
        layout_msg.addStretch()
        layout_msg.addWidget(self.lbl_msg_text)
        layout_msg.addWidget(self.lbl_countdown, alignment=Qt.AlignmentFlag.AlignCenter)
        layout_msg.addStretch()
        
        col_center.addWidget(self.frame_msg, stretch=2)

        # C. Operator Controls Row (Temp, E-Stop, Legend)
        operator_controls_layout = QHBoxLayout()
        operator_controls_layout.setSpacing(20)

        # C1. Temperature Display
        self.frame_temp = QFrame(objectName="ControlCard")
        layout_temp = QVBoxLayout(self.frame_temp)
        layout_temp.setContentsMargins(0,0,0,10)
        
        lbl_temp_title = QLabel("CORE TEMP", objectName="Title")
        lbl_temp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_temp.addWidget(lbl_temp_title)
        
        layout_temp.addStretch()
        row_temp_val = QHBoxLayout()
        row_temp_val.addStretch()
        self.lbl_temp_value = QLabel("0.0", objectName="Value")
        row_temp_val.addWidget(self.lbl_temp_value)
        row_temp_val.addWidget(QLabel("°C", objectName="Unit"), alignment=Qt.AlignmentFlag.AlignBottom)
        row_temp_val.addStretch()
        layout_temp.addLayout(row_temp_val)
        layout_temp.addStretch()
        operator_controls_layout.addWidget(self.frame_temp, stretch=1)

        # C2. E-Stop Button
        self.frame_estop = QFrame(objectName="ActionCard")
        layout_estop = QVBoxLayout(self.frame_estop)
        layout_estop.setContentsMargins(0,0,0,10)
        
        lbl_estop_title = QLabel("EMERGENCY STOP", objectName="Title")
        lbl_estop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_estop.addWidget(lbl_estop_title)
        
        layout_estop.addStretch()
        self.btn_estop = EmergencyStopButton()
        self.btn_estop.callback = self.handle_estop_toggle
        layout_estop.addWidget(self.btn_estop, alignment=Qt.AlignmentFlag.AlignCenter)
        layout_estop.addStretch()
        operator_controls_layout.addWidget(self.frame_estop, stretch=1)

        # C3. Legend/Status Key
        frame_legend = QFrame(objectName="ControlCard")
        layout_legend = QVBoxLayout(frame_legend)
        layout_legend.setContentsMargins(0,0,0,10)
        
        lbl_legend_title = QLabel("LOCAL PANEL", objectName="Title")
        lbl_legend_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_legend.addWidget(lbl_legend_title)
        
        layout_legend.addStretch()
        grid_legend = QGridLayout()
        grid_legend.setSpacing(10)
        grid_legend.setContentsMargins(15, 0, 15, 0)
        
        # Helper to create legend items
        self.create_legend_tile(grid_legend, 0, 0, "norm", "#00E676", "NORMAL TEMP")
        self.create_legend_tile(grid_legend, 0, 1, "warn", "#FFC107", "HIGH TEMP")
        self.create_legend_tile(grid_legend, 1, 0, "dang", "#FF5252", "CRITICAL TEMP")
        self.create_legend_tile(grid_legend, 1, 1, "stop", "#448AFF", "FAN RUNNING") 
        
        layout_legend.addLayout(grid_legend)
        layout_legend.addStretch()
        operator_controls_layout.addWidget(frame_legend, stretch=1)

        col_center.addLayout(operator_controls_layout, stretch=3)

        # D. Trend Chart
        frame_chart = QFrame(objectName="Card")
        layout_chart = QVBoxLayout(frame_chart)
        layout_chart.setContentsMargins(0,0,0,5)
        
        lbl_chart_title = QLabel("TEMPERATURE TREND", objectName="Title")
        lbl_chart_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_chart.addWidget(lbl_chart_title)
        
        self.chart_canvas = TrendChart()
        # Initial plot line setup
        self.chart_line, = self.chart_canvas.ax.plot(self.data_x, self.data_y, c='#03DAC6', lw=2)
        layout_chart.addWidget(self.chart_canvas)
        col_center.addWidget(frame_chart, stretch=3)
        
        content_layout.addLayout(col_center, stretch=55)

        # --- RIGHT COLUMN: VISUALIZATION ---
        col_right = QVBoxLayout()
        self.frame_vis = QFrame(objectName="Card")
        layout_vis = QVBoxLayout(self.frame_vis)
        layout_vis.setContentsMargins(0,0,0,20)
        
        lbl_vis_title = QLabel("COOLING FAN", objectName="Title")
        lbl_vis_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_vis.addWidget(lbl_vis_title)
        
        layout_vis.addStretch()
        self.lbl_runtime = QLabel("RUN TIME: 00:00:00")
        self.lbl_runtime.setStyleSheet("color: #888; font-family: Consolas; font-size: 16px; letter-spacing: 1px;")
        layout_vis.addWidget(self.lbl_runtime, alignment=Qt.AlignmentFlag.AlignCenter)
        layout_vis.addSpacing(20)
        
        self.turbine_widget = TurbineWidget()
        layout_vis.addWidget(self.turbine_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout_vis.addStretch()
        self.lbl_status_text = QLabel("READY", objectName="StatusLabel")
        self.lbl_status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_vis.addWidget(self.lbl_status_text)
        layout_vis.addSpacing(10)
        
        col_right.addWidget(self.frame_vis)
        content_layout.addLayout(col_right, stretch=25)

        main_layout.addLayout(content_layout)

    def create_legend_tile(self, grid: QGridLayout, row: int, col: int, key: str, color_hex: str, text: str) -> None:
        """
        Helper method to create consistent legend tiles.
        
        Args:
            grid (QGridLayout): The layout to add the tile to.
            row (int): Grid row index.
            col (int): Grid column index.
            key (str): Unique internal identifier for the legend item.
            color_hex (str): Color associated with the status.
            text (str): Display text.
        """
        tile = QFrame()
        tile.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
            }
        """)
        tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QHBoxLayout(tile)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        dot = QLabel()
        dot.setFixedSize(20, 20)
        dot.setStyleSheet(f"background-color: transparent; border: 2px solid #555; border-radius: 10px;")
        
        label = QLabel(text)
        label.setStyleSheet("color: #666; font-size: 12px; font-weight: normal;")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(dot)
        layout.addWidget(label)
        
        grid.addWidget(tile, row, col)
        
        # Store references for dynamic updates later
        self.legend_items[key] = {
            "dot": dot, 
            "label": label, 
            "col": color_hex,
            "tile": tile
        }

    def setup_serial(self) -> None:
        """
        Initializes the serial connection.
        Attempts to connect to the physical port. If unsuccessful, falls back to MockSerial.
        """
        self.serial_connection: Union[serial.Serial, MockSerial, None] = None
        
        if not USE_SIMULATION:
            try:
                # Attempt to open real serial port
                self.serial_connection = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
                self.log_event(f"SYS: Port Open ({PORT})")
            except serial.SerialException:
                self.log_event(f"ERR: Port Fail ({PORT})")
        
        if self.serial_connection is None:
            if not USE_SIMULATION:
                self.log_event("SYS: Switching to Sim (Fail)")
                
            # Fallback to Mock
            self.serial_connection = MockSerial()
            if USE_SIMULATION:
                self.log_event("SYS: Sim Mode Active")

    def log_event(self, message: str) -> None:
        """
        Adds a timestamped, color-coded entry to the operator log.
        
        Args:
            message (str): The text message to log.
        """
        # Ensure log doesn't grow indefinitely
        if self.log_widget.count() >= MAX_LOG_ENTRIES:
            self.log_widget.takeItem(0)
            
        timestamp = datetime.now().strftime('%H:%M:%S')
        item = QListWidgetItem(f"[{timestamp}] {message}")
        
        # Font setup
        font = item.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        
        # Color Coding Logic based on keywords
        msg = message.upper()
        if any(k in msg for k in ["ERR", "FAIL", "CRITICAL", "ALARM", "STOPPED", "HALTED", "EMERGENCY", "DANGER"]):
            item.setForeground(QColor("#FF5252")) # Red
            font.setBold(True) 
        elif any(k in msg for k in ["WARN", "HIGH", "ATTENTION"]):
            item.setForeground(QColor("#FFD740")) # Amber
            font.setBold(False)
        elif any(k in msg for k in ["SYS: PORT OPEN", "RESUMED", "NORMAL", "READY", "SUCCESS"]):
            item.setForeground(QColor("#69F0AE")) # Green
            font.setBold(False)
        elif any(k in msg for k in ["OP:", "SYS:", "INIT"]):
            item.setForeground(QColor("#40C4FF")) # Cyan
            font.setBold(False)
        else:
            item.setForeground(QColor("#B0BEC5")) # Grey
            font.setBold(False)

        item.setFont(font)
        self.log_widget.addItem(item)
        self.log_widget.scrollToBottom()

    def get_temp_state_key(self, temp: float) -> str:
        """
        Determines the status key string based on current temperature.
        
        Args:
            temp (float): Current temperature.
        
        Returns:
            str: 'norm', 'warn', or 'dang'.
        """
        if temp < TEMP_THRESHOLD_WARNING: return "norm"
        if temp < TEMP_THRESHOLD_CRITICAL: return "warn"
        return "dang"

    def determine_system_state(self, temp: float) -> Tuple[QColor, float, str, str]:
        """
        Calculates the overall system state vector.
        
        Args:
            temp (float): Current temperature input.
            
        Returns:
            Tuple containing:
            1. QColor: Visual indicator color.
            2. float: Target turbine velocity.
            3. str: Human-readable status text.
            4. str: Internal state key.
        """
        # Priority 1: Emergency Stop (Software or Hardware)
        if self.is_estopped:
            return QColor("#750611"), 0, "EMERGENCY STOP", "stop"
        
        if self.is_hard_paused:
             return QColor("#750611"), 0, "FAN STOPPED", "stop"

        # Priority 2: Temperature Thresholds
        if temp < TEMP_THRESHOLD_WARNING:
            return QColor("#00E676"), CONSTANT_FAN_SPEED, "NORMAL", "norm"
        if temp < TEMP_THRESHOLD_CRITICAL:
            return QColor("#FFC107"), CONSTANT_FAN_SPEED, "HIGH TEMPERATURE", "warn"
            
        # Priority 3: Critical State (Danger)
        return QColor("#FF5252"), CONSTANT_FAN_SPEED, "DANGER", "dang"

    def refresh_legend(self) -> None:
        """
        Updates the legend widget to highlight the active state.
        This provides visual feedback on what the current colors mean.
        """
        active_temp_key = self.get_temp_state_key(self.current_temp)
        
        # Iterate through temp states
        for key in ["norm", "warn", "dang"]:
            item = self.legend_items[key]
            color = item['col']
            
            if key == active_temp_key:
                # Active: Fill dot, Bold Text, Light Background
                item['dot'].setStyleSheet(f"background-color: {color}; border: 2px solid {color}; border-radius: 10px;")
                item['label'].setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
                item['tile'].setStyleSheet("background-color: #383838; border: 1px solid #555; border-radius: 8px;")
            else:
                # Inactive: Outline dot, Dim Text, Dark Background
                item['dot'].setStyleSheet(f"background-color: transparent; border: 2px solid #555; border-radius: 10px;")
                item['label'].setStyleSheet("color: #666; font-weight: normal; font-size: 12px;")
                item['tile'].setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px;")

        # Handle Fan State Legend Item
        is_fan_running = not (self.is_estopped or self.is_hard_paused)
        stop_item = self.legend_items["stop"]
        fan_color = stop_item['col'] 

        if is_fan_running:
            stop_item['dot'].setStyleSheet(f"background-color: {fan_color}; border: 2px solid {fan_color}; border-radius: 10px;")
            stop_item['label'].setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
            stop_item['tile'].setStyleSheet("background-color: #383838; border: 1px solid #555; border-radius: 8px;")
        else:
            stop_item['dot'].setStyleSheet("background-color: transparent; border: 2px solid #555; border-radius: 10px;")
            stop_item['label'].setStyleSheet("color: #666; font-weight: normal; font-size: 12px;")
            stop_item['tile'].setStyleSheet("background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px;")

    def handle_estop_toggle(self, is_stopped: bool) -> None:
        """
        Handles the transition logic when E-Stop is toggled.
        
        Args:
            is_stopped (bool): True if Stop requested, False if Reset requested.
        """
        self.is_estopped = is_stopped
        status_msg = "HALTED" if self.is_estopped else "RESUMED"
        
        if is_stopped:
            self.log_event(f"ALARM: E-STOP {status_msg}")
            # Show the modal overlay
            self.overlay.setVisible(True)
            self.overlay.raise_()
        else:
            self.log_event(f"OP: E-STOP {status_msg}")
            # Hide the overlay
            self.overlay.setVisible(False)
            # Reset countdown state
            self.countdown_val = COUNTDOWN_START_SECONDS
            self.is_countdown_active = False
            self.current_severity = "normal"

        # Hardware Command Transmission
        if self.serial_connection and not USE_SIMULATION:
            try:
                command = b'0' if is_stopped else b'1'
                self.serial_connection.write(command)
            except Exception as e:
                print(f"Failed to send command: {e}")
        
        # Sync Button Visual State (if triggered programmatically)
        if self.btn_estop.is_active != is_stopped:
            self.btn_estop.is_active = is_stopped
            self.btn_estop.update()

        self.refresh_legend()

    def update_seconds_logic(self) -> None:
        """
        Low-frequency logic loop (1 Hz).
        
        Responsibilities:
        - Update Runtime counter.
        - Process Auto-Shutdown Countdown logic.
        - Check for Critical Temperature duration.
        """
        # Safety Check: If already stopped, do not run countdown logic.
        is_emergency = self.is_estopped or self.is_hard_paused

        if is_emergency:
            # Force UI to update text to "Stopped" state even if temp is high
            self.update_countdown_ui(is_danger=False, is_emergency=True)
            return

        # Increment Runtime
        self.runtime_seconds += 1
        hours, remainder = divmod(self.runtime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.lbl_runtime.setText(f"RUN TIME: {hours:02}:{minutes:02}:{seconds:02}")
        
        # Countdown Logic:
        # If temp > Critical, start counting down. If it drops, reset.
        if self.current_temp >= TEMP_THRESHOLD_CRITICAL:
            if not self.is_countdown_active:
                self.is_countdown_active = True
                self.countdown_val = COUNTDOWN_START_SECONDS
            
            if self.countdown_val > 0:
                self.countdown_val -= 1
            
            # Trigger Auto E-Stop if timer expires
            if self.countdown_val <= 0:
                self.current_severity = "critical"
                self.log_event("ALARM: TIMER EXPIRED - INITIATING AUTO E-STOP")
                self.handle_estop_toggle(True)
                return
                
            elif self.countdown_val <= 5:
                self.current_severity = "critical"
            else:
                self.current_severity = "danger"

            self.update_countdown_ui(is_danger=True)
            
        elif self.current_temp >= TEMP_THRESHOLD_WARNING:
             self.current_severity = "warning"
             self.is_countdown_active = False
             self.countdown_val = COUNTDOWN_START_SECONDS
             self.update_countdown_ui(is_danger=False)
        else:
            self.current_severity = "normal"
            self.is_countdown_active = False
            self.countdown_val = COUNTDOWN_START_SECONDS
            self.update_countdown_ui(is_danger=False)

    def update_countdown_ui(self, is_danger: bool = False, is_emergency: bool = False) -> None:
        """
        Updates the central message card and countdown display.
        
        Args:
            is_danger (bool): If True, shows the countdown timer.
            is_emergency (bool): If True, shows "System Halted" message.
        """
        self.lbl_countdown.setVisible(False)

        # Case 1: System is Stopped
        if is_emergency:
            if self.is_estopped:
                self.lbl_msg_text.setText("EMERGENCY MODE ACTIVE\n!!! FAN STOPPED !!!")
            elif self.is_hard_paused:
                self.lbl_msg_text.setText("FAN STOPPED")
            self.lbl_msg_text.setStyleSheet("color: #FF5252; font-size: 26px; font-weight: bold;")
            return

        # Case 2: Imminent Danger (Countdown)
        if is_danger:
             self.lbl_countdown.setVisible(True)
             self.lbl_msg_text.setText("CRITICAL TEMP !!!\nSTOP FAN WITHIN:")
             self.lbl_msg_text.setStyleSheet("color: #FF5252; font-size: 24px; font-weight: bold;")
             
             hours, remainder = divmod(self.countdown_val, 3600)
             minutes, seconds = divmod(remainder, 60)
             self.lbl_countdown.setText(f"{hours:02}:{minutes:02}:{seconds:02}")
             
             if self.countdown_val <= 5:
                 self.lbl_countdown.setStyleSheet("color: #FF5252;")
             else:
                 self.lbl_countdown.setStyleSheet("color: #FFC107;")
             return

        # Case 3: Warning (High Temp)
        if self.current_temp >= TEMP_THRESHOLD_WARNING:
             self.lbl_msg_text.setText("WARNING\nHIGH TEMPERATURE")
             self.lbl_msg_text.setStyleSheet("color: #FFC107; font-size: 28px; font-weight: bold;")
             return

        # Case 4: Normal
        self.lbl_msg_text.setText("TEMPERATURE LEVELS SAFE...\nMONITORING ACTIVE.")
        self.lbl_msg_text.setStyleSheet("color: #00E676; font-size: 28px; font-weight: bold;")

    def update_alarm_visuals(self) -> None:
        """
        Performs visual updates based on alarm severity (e.g., flashing borders).
        This is called every animation frame.
        """
        t = time.time()
        border_style = "border-radius: 12px; border: 2px solid #333;"
        
        if self.current_severity == "critical":
            # Fast Flash Red (1Hz)
            if (t * 2) % 2 < 1:
                border_color = "#FF5252"
                bg_color = "#3a0e0e"
            else:
                border_color = "#750611"
                bg_color = "#1e1e1e"
            border_style = f"border-radius: 12px; border: 3px solid {border_color}; background-color: {bg_color};"
            
        elif self.current_severity == "danger":
             # Slow Pulse Red
             intensity = (math.sin(t * 5) + 1) / 2
             border_style = f"border-radius: 12px; border: 2px solid rgba(255, 82, 82, {150 + int(intensity*100)});"
             
        elif self.current_severity == "warning":
            # Slow Pulse Yellow
            intensity = (math.sin(t * 3) + 1) / 2 
            border_style = f"border-radius: 12px; border: 2px solid rgba(255, 193, 7, {150 + int(intensity*100)});"

        # Apply computed styles to critical frames
        self.frame_msg.setStyleSheet(f"QFrame#MessageCard {{ {border_style} }}")
        self.frame_temp.setStyleSheet(f"QFrame#ControlCard {{ {border_style} }}")
        self.frame_log.setStyleSheet(f"QFrame#Card {{ {border_style} }}")
        self.frame_vis.setStyleSheet(f"QFrame#Card {{ {border_style} }}")

    def update_alarm_banner(self) -> None:
        """Updates the top banner text and color based on overall system state."""
        base_style = "color: #fff; font-weight: bold; border-radius: 4px; font-size: 18px;"
        _, _, _, state_key = self.determine_system_state(self.current_temp)

        if state_key == "stop":
            if self.is_estopped:
                text = "ALARM: EMERGENCY STOP"
                style = f"background: #FF5252; {base_style}"
            else:
                text = "COOLING FAN - STOPPED"
                style = f"background: #750611; {base_style}"
        elif state_key == "dang":
            text = "ALARM: VERY HIGH TEMP"
            style = f"background: #FF5252; {base_style}"
        elif state_key == "warn":
            text = "WARNING: HIGH TEMPERATURE"
            style = f"background: #FFC107; color: #000; font-weight: bold; border-radius: 4px; font-size: 18px;"
        else:
            text = "COOLING FAN - RUNNING"
            style = f"background: #00E676; color: #000; font-weight: bold; border-radius: 4px; font-size: 18px;"
            
        self.lbl_alarm_banner.setText(text)
        self.lbl_alarm_banner.setStyleSheet(style)

    def update_animation(self) -> None:
        """
        High-frequency loop (~60fps).
        
        Responsibilities:
        - Update Physics (Turbine velocity/angle).
        - Trigger Repaints.
        - Handle State determination.
        """
        color, target_velocity, status_text, _ = self.determine_system_state(self.current_temp)
        
        self.update_alarm_visuals()
        
        # Simple Rotation (No Physics/Inertia)
        # Directly apply the target velocity to the angle
        self.turbine_angle = (self.turbine_angle + target_velocity) % 360
        self.turbine_widget.update_state(self.turbine_angle, color)
        
        self.lbl_status_text.setText(status_text)
        self.lbl_status_text.setStyleSheet(f"color: {color.name()}; font-weight: bold; font-size: 16px;")
        
        self.update_alarm_banner()
        self.refresh_legend()
        
        # Log Status Changes
        if status_text != self.system_status:
            if self.system_status != "": 
                self.log_event(f"STATUS: {status_text}")
            self.system_status = status_text

    def read_serial_data(self) -> None:
        """
        Reads data from the serial port or simulation.
        Parsing logic handles partial reads and format errors.
        """
        try:
            # 1. READ FROM HARDWARE
            if self.serial_connection and not isinstance(self.serial_connection, MockSerial):
                if self.serial_connection.in_waiting:
                    # Decode and split lines
                    raw_data = self.serial_connection.read_all().decode('utf-8', errors='ignore')
                    lines = raw_data.strip().split('\n')
                    
                    # Process only the most recent complete line
                    for line in reversed(lines):
                        line = line.strip()
                        if not line: continue
                        
                        if "ERROR" in line:
                             self.lbl_msg_text.setText("SENSOR ERROR - CHECK CONNECTION")
                             self.lbl_msg_text.setStyleSheet("color: #FF5252; font-weight: bold;")
                             continue

                        if "," in line:
                            parts = line.split(",")
                            if len(parts) >= 3:
                                try:
                                    self.current_temp = float(parts[1])
                                    status_flag = int(parts[2])
                                    self.is_hard_paused = (status_flag == 0)
                                    break 
                                except ValueError:
                                    continue
            
            # 2. READ FROM MOCK
            elif isinstance(self.serial_connection, MockSerial):
                 raw_data = self.serial_connection.read_all().decode('utf-8', errors='ignore')
                 parts = raw_data.strip().split(",")
                 if len(parts) >= 3:
                     self.current_temp = float(parts[1])
                     status_flag = int(parts[2])
                     self.is_hard_paused = (status_flag == 0)

        except Exception as e:
            print(f"Serial Read Error: {e}")
            self.log_event("ERR: Connection Lost")

        # 3. UPDATE UI ELEMENTS
        self.lbl_temp_value.setText(f"{self.current_temp:.1f}")
        
        # 4. UPDATE CHART ARRAYS (Scrolling Buffer)
        self.data_y = np.roll(self.data_y, -1)
        self.data_y[-1] = self.current_temp
        self.chart_line.set_ydata(self.data_y)
        
        # 5. DYNAMIC Y-AXIS SCALING
        min_y, max_y = np.min(self.data_y), np.max(self.data_y)
        if (max_y - min_y) < 5:
            # Keep minimum 10 degree window
            mid_y = (max_y + min_y) / 2
            self.chart_canvas.ax.set_ylim(mid_y - 5, mid_y + 5)
        else:
            self.chart_canvas.ax.set_ylim(min_y - 2, max_y + 2)
            
        self.chart_canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScadaDashboard()
    window.showMaximized()
    sys.exit(app.exec())