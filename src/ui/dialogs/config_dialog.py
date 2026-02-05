import copy
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel, QLineEdit, QMessageBox, QInputDialog, QSplitter, QWidget,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QTabWidget, QFrame, QSpinBox, QSlider,
    QListWidgetItem, QColorDialog, QFormLayout, QComboBox
)
from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush
from src.models.config import generate_random_color
from src.services.date_stamp_service import kelvin_to_rgb


class TemperatureGradientPreview(QWidget):
    """Widget that displays a color temperature gradient preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.temp_outer = 1800
        self.temp_core = 6500
        self.setMinimumHeight(40)
        self.setMaximumHeight(40)

    def set_temperatures(self, temp_outer: int, temp_core: int):
        """Update the temperature range and repaint."""
        self.temp_outer = temp_outer
        self.temp_core = temp_core
        self.update()

    def paintEvent(self, event):
        """Draw the gradient preview."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create gradient from outer (warm) to core (hot)
        gradient = QLinearGradient(0, 0, self.width(), 0)

        # Generate colors at various positions
        num_stops = 9
        for i in range(num_stops):
            pos = i / (num_stops - 1)
            temp = self.temp_outer + (self.temp_core - self.temp_outer) * pos
            r, g, b = kelvin_to_rgb(int(temp))
            gradient.setColorAt(pos, QColor(r, g, b))

        # Draw rounded rectangle with gradient
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#555"), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 5, 5)

        # Draw temperature labels
        painter.setPen(QColor("#333"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(5, self.height() - 8, f"{self.temp_outer}K")
        painter.drawText(self.width() - 45, self.height() - 8, f"{self.temp_core}K")

        painter.end()


class ConfigDialog(QDialog):
    """Configuration window for size groups and their sizes."""

    def __init__(self, config, project_manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.project_manager = project_manager

        # Working copy for editing (changes only apply on save)
        self.working_copy_size_groups = copy.deepcopy(config.size_groups)

        # Track original state for deletion detection
        self.original_size_group_names = set(config.size_groups.keys())
        self.original_sizes_per_group = {}
        for group_name, group_data in config.size_groups.items():
            if isinstance(group_data, dict) and "sizes" in group_data:
                self.original_sizes_per_group[group_name] = {
                    size["ratio"] for size in group_data["sizes"]
                }

        self.setWindowTitle("Size Group Configuration")
        self.resize(800, 500)

        # Date stamp widget attributes (created in create_date_stamp_tab)
        self.physical_height_spinbox: QDoubleSpinBox
        self.format_input: QLineEdit
        self.position_combo: QComboBox
        self.gradient_preview: TemperatureGradientPreview
        self.outer_temp_slider: QSlider
        self.core_temp_slider: QSlider
        self.glow_spinbox: QSpinBox
        self.margin_spinbox: QSpinBox
        self.opacity_spinbox: QSpinBox

        self.init_ui()

    def init_ui(self):
        """Create the tabbed interface."""
        main_layout = QVBoxLayout()

        # Create tab widget
        tab_widget = QTabWidget()

        # Tab 1: Directory settings
        directory_tab = self.create_directory_tab()
        tab_widget.addTab(directory_tab, "Directory")

        # Tab 2: Size groups
        size_group_tab = self.create_size_group_tab()
        tab_widget.addTab(size_group_tab, "Size group")

        # Tab 3: Cost settings
        cost_tab = self.create_cost_tab()
        tab_widget.addTab(cost_tab, "Cost")

        # Tab 4: Screen Calibration
        calibration_tab = self.create_calibration_tab()
        tab_widget.addTab(calibration_tab, "Screen Calibration")

        # Tab 5: Date Stamp
        date_stamp_tab = self.create_date_stamp_tab()
        tab_widget.addTab(date_stamp_tab, "Date Stamp")

        main_layout.addWidget(tab_widget)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_changes)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

        # Load initial data
        self.load_size_groups()

    def create_directory_tab(self):
        """Create directory settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Workspace directory row
        workspace_layout = QHBoxLayout()
        workspace_label = QLabel("Workspace Directory:")
        workspace_layout.addWidget(workspace_label)

        # Get current workspace directory from settings
        current_workspace = self.config.get_setting("workspace_directory", "")
        self.workspace_input = QLineEdit()
        self.workspace_input.setText(current_workspace)
        self.workspace_input.setPlaceholderText("Select a folder for storing projects")
        workspace_layout.addWidget(self.workspace_input)

        # Browse button
        workspace_browse_btn = QPushButton("Browse...")
        workspace_browse_btn.clicked.connect(self.browse_workspace_directory)
        workspace_layout.addWidget(workspace_browse_btn)

        layout.addLayout(workspace_layout)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("margin: 20px 0;")
        layout.addWidget(separator)

        # Mouse shortcuts reminder section
        shortcuts_title = QLabel("Mouse Shortcuts:")
        shortcuts_title.setStyleSheet("font-weight: bold; font-size: 13px; margin-top: 10px;")
        layout.addWidget(shortcuts_title)

        shortcuts_info = QLabel(
            "Left click (Single): Apply selected size group and size tags to image\n"
            "Left double click: Clear all tags from image\n"
            "Right click: Select image for actions (Find Similar, Rotate, etc.)\n"
            "Right double click: View image detail"
        )
        shortcuts_info.setStyleSheet("color: #555; margin-left: 10px; margin-top: 5px; line-height: 1.5;")
        layout.addWidget(shortcuts_info)

        # Add stretch to push content to top
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def browse_workspace_directory(self):
        """Browse for workspace directory."""
        current = self.workspace_input.text()
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Workspace Directory",
            current if current else ""
        )
        if folder:
            self.workspace_input.setText(folder)

    def create_size_group_tab(self):
        """Create size group settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Create splitter for two-panel layout
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Size Groups
        left_panel = self.create_size_groups_panel()
        splitter.addWidget(left_panel)

        # Right panel: Sizes in selected group
        right_panel = self.create_sizes_panel()
        splitter.addWidget(right_panel)

        # Set initial splitter sizes (30% left, 70% right)
        splitter.setSizes([250, 550])

        layout.addWidget(splitter)
        tab.setLayout(layout)
        return tab

    def create_cost_tab(self):
        """Create cost settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Info label
        info_label = QLabel("Set the cost for each print size (used to calculate total cost):")
        info_label.setStyleSheet("color: #666;")
        layout.addWidget(info_label)

        # Table for size costs
        self.costs_table = QTableWidget()
        self.costs_table.setColumnCount(2)
        self.costs_table.setHorizontalHeaderLabels(["Size", "Cost"])
        self.costs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.costs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.costs_table.setColumnWidth(1, 150)
        self.costs_table.verticalHeader().setVisible(False)

        layout.addWidget(self.costs_table)

        # Load initial costs
        self.load_size_costs()

        # Add stretch to allow table to expand
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def load_size_costs(self):
        """Load size costs into the table."""
        # Get all unique sizes from all groups
        unique_sizes = self.config.get_all_unique_sizes()

        # Get current costs
        current_costs = self.config.get_all_size_costs()

        self.costs_table.setRowCount(len(unique_sizes))
        self.cost_spinboxes = {}

        for row, size_ratio in enumerate(unique_sizes):
            # Size label (read-only)
            size_item = QTableWidgetItem(size_ratio)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.costs_table.setItem(row, 0, size_item)

            # Cost spinbox (use C locale to accept period as decimal separator)
            cost_spinbox = QDoubleSpinBox()
            cost_spinbox.setLocale(QLocale(QLocale.Language.C))
            cost_spinbox.setRange(0, 999999)
            cost_spinbox.setDecimals(2)
            cost_spinbox.setValue(current_costs.get(size_ratio, 0))
            self.costs_table.setCellWidget(row, 1, cost_spinbox)
            self.cost_spinboxes[size_ratio] = cost_spinbox

    def create_calibration_tab(self):
        """Create screen calibration tab for real-size preview."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Title and instruction
        title_label = QLabel("Screen Calibration for Real-Size Preview")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        instruction_label = QLabel(
            "Adjust the line below until it matches one unit on your ruler.\n"
            "This calibration is used to preview images at their real print size.\n"
            "For example, if your sizes are in inches, adjust until the line equals 1 inch."
        )
        instruction_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Calibration line widget
        self.calibration_line = CalibrationLineWidget()
        current_ppu = self.config.get_setting("pixels_per_unit", 100)
        self.calibration_line.set_length(current_ppu)
        layout.addWidget(self.calibration_line)

        # Control buttons and display
        control_layout = QHBoxLayout()

        # Decrease buttons
        decrease_10_btn = QPushButton("◀◀ -10")
        decrease_10_btn.clicked.connect(lambda: self.adjust_calibration(-10))
        control_layout.addWidget(decrease_10_btn)

        decrease_1_btn = QPushButton("◀ -1")
        decrease_1_btn.clicked.connect(lambda: self.adjust_calibration(-1))
        control_layout.addWidget(decrease_1_btn)

        # Current value display with spinbox
        self.calibration_spinbox = QSpinBox()
        self.calibration_spinbox.setRange(10, 1000)
        self.calibration_spinbox.setValue(current_ppu)
        self.calibration_spinbox.setSuffix(" px")
        self.calibration_spinbox.valueChanged.connect(self.on_calibration_spinbox_changed)
        control_layout.addWidget(self.calibration_spinbox)

        # Increase buttons
        increase_1_btn = QPushButton("+1 ▶")
        increase_1_btn.clicked.connect(lambda: self.adjust_calibration(1))
        control_layout.addWidget(increase_1_btn)

        increase_10_btn = QPushButton("+10 ▶▶")
        increase_10_btn.clicked.connect(lambda: self.adjust_calibration(10))
        control_layout.addWidget(increase_10_btn)

        layout.addLayout(control_layout)

        # Info label
        info_label = QLabel(
            "The line length in pixels represents one unit of measurement.\n"
            "Use keyboard arrow keys (← →) for fine adjustment when buttons are focused."
        )
        info_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 15px;")
        layout.addWidget(info_label)

        # Add stretch to push content to top
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def adjust_calibration(self, delta: int):
        """Adjust the calibration line length."""
        current = self.calibration_line.length
        new_value = max(10, min(1000, current + delta))
        self.calibration_line.set_length(new_value)
        self.calibration_spinbox.setValue(new_value)

    def on_calibration_spinbox_changed(self, value: int):
        """Handle spinbox value change."""
        self.calibration_line.set_length(value)

    def _create_spinbox_row(self, widget_attr, min_val, max_val, default, suffix="", step=None, decimals=None, hint=None):
        """Helper to create a spinbox row with consistent formatting.

        Args:
            widget_attr: Attribute name to store the spinbox (e.g., "physical_height_spinbox")
            min_val: Minimum value
            max_val: Maximum value
            default: Default value from settings
            suffix: Unit suffix (e.g., " units", "%")
            step: Step increment (optional)
            decimals: Number of decimal places (creates QDoubleSpinBox if set)
            hint: Help text to display next to spinbox (optional)
        """
        layout = QHBoxLayout()

        # Create appropriate spinbox type
        if decimals is not None:
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(decimals)
            if step is not None:
                spinbox.setSingleStep(step)
        else:
            spinbox = QSpinBox()
            if step is not None:
                spinbox.setSingleStep(step)

        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default)
        if suffix:
            spinbox.setSuffix(suffix)

        layout.addWidget(spinbox)
        if hint:
            layout.addWidget(QLabel(f"({hint})"))
        layout.addStretch()

        setattr(self, widget_attr, spinbox)
        return layout

    def _create_temp_slider(self, widget_attr, min_val, max_val, default, tick_interval):
        """Helper to create a temperature slider with labels.

        Args:
            widget_attr: Attribute name to store the slider
            min_val: Minimum temperature (K)
            max_val: Maximum temperature (K)
            default: Default value from settings
            tick_interval: Tick mark spacing
        """
        layout = QHBoxLayout()

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(tick_interval)
        slider.valueChanged.connect(self._update_gradient_preview)

        layout.addWidget(QLabel("Warmer"))
        layout.addWidget(slider)
        layout.addWidget(QLabel("Cooler"))

        setattr(self, widget_attr, slider)
        return layout

    def create_date_stamp_tab(self):
        """Create date stamp settings tab."""
        tab = QWidget()
        layout = QVBoxLayout()

        # Title and instructions
        title_label = QLabel("Vintage Date Stamp Settings")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        instruction_label = QLabel(
            "Configure the vintage film camera-style date stamp that appears on exported images.\n"
            "The stamp height is in the same units as your print sizes (e.g., cm or inches).\n"
            "Example: 0.5 height on a 9x6 print = 0.5/6 ≈ 8% of image height."
        )
        instruction_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Settings form
        form_layout = QFormLayout()

        # Physical dimensions
        form_layout.addRow(
            "Stamp Height:",
            self._create_spinbox_row("physical_height_spinbox", 0.1, 2.0,
                                    self.config.get_setting("date_stamp_physical_height", 0.5),
                                    suffix=" units", step=0.1, decimals=2,
                                    hint="Physical height in same units as print size (cm/inches)")
        )

        # Date format with examples
        format_layout = QVBoxLayout()
        self.format_input = QLineEdit()
        self.format_input.setText(self.config.get_setting("date_stamp_format", "YY.MM.DD"))
        self.format_input.setPlaceholderText("YY.MM.DD")
        format_layout.addWidget(self.format_input)

        format_examples = QLabel("Examples: YY.MM.DD → 25.12.23 | MM.DD.YY → 12.25.25 | DD-MM-YY → 25-12-23")
        format_examples.setStyleSheet("color: #888; font-size: 10px;")
        format_layout.addWidget(format_examples)

        format_note = QLabel("Note: Use only numbers, dots (.), dashes (-), and spaces. Avoid apostrophes or special characters.")
        format_note.setStyleSheet("color: #FF6600; font-size: 10px; font-style: italic;")
        format_layout.addWidget(format_note)
        form_layout.addRow("Date Format:", format_layout)

        # Position
        position_layout = QHBoxLayout()
        self.position_combo = QComboBox()
        self.position_combo.addItems(["bottom-right", "bottom-left", "top-right", "top-left"])
        self.position_combo.setCurrentText(self.config.get_setting("date_stamp_position", "bottom-right"))
        position_layout.addWidget(self.position_combo)
        position_layout.addStretch()
        form_layout.addRow("Position:", position_layout)

        # Temperature gradient section
        gradient_label = QLabel("Color Temperature Gradient:")
        gradient_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        form_layout.addRow(gradient_label)

        self.gradient_preview = TemperatureGradientPreview()
        form_layout.addRow(self.gradient_preview)

        form_layout.addRow(
            "Outer Glow:",
            self._create_temp_slider("outer_temp_slider", 1000, 4000,
                                    self.config.get_setting("date_stamp_temp_outer", 1800), 500)
        )

        form_layout.addRow(
            "Core Text:",
            self._create_temp_slider("core_temp_slider", 4000, 10000,
                                    self.config.get_setting("date_stamp_temp_core", 6500), 1000)
        )

        # Initialize gradient preview
        self._update_gradient_preview()

        # Appearance settings
        form_layout.addRow(
            "Glow Intensity:",
            self._create_spinbox_row("glow_spinbox", 0, 100,
                                    self.config.get_setting("date_stamp_glow_intensity", 80),
                                    suffix="%")
        )

        form_layout.addRow(
            "Margin from Edge:",
            self._create_spinbox_row("margin_spinbox", 10, 100,
                                    self.config.get_setting("date_stamp_margin", 30),
                                    suffix=" px")
        )

        form_layout.addRow(
            "Opacity:",
            self._create_spinbox_row("opacity_spinbox", 50, 100,
                                    self.config.get_setting("date_stamp_opacity", 90),
                                    suffix="%")
        )

        layout.addLayout(form_layout)

        # Preview section
        preview_label = QLabel("Preview:")
        preview_label.setStyleSheet("font-weight: bold; margin-top: 20px;")
        layout.addWidget(preview_label)

        preview_info = QLabel(
            "Date stamp preview will appear on images when you mark them with 'Add Date Stamp' button.\n"
            "The actual rendering uses multi-layer glow effects for authentic vintage appearance."
        )
        preview_info.setStyleSheet("color: #888; font-size: 11px;")
        preview_info.setWordWrap(True)
        layout.addWidget(preview_info)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _update_gradient_preview(self):
        """Update the gradient preview widget with current slider values."""
        temp_outer = self.outer_temp_slider.value()
        temp_core = self.core_temp_slider.value()
        self.gradient_preview.set_temperatures(temp_outer, temp_core)

    def create_size_groups_panel(self):
        """Create left panel with size group list."""
        panel = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Size Groups:")
        label.setStyleSheet("font-weight: bold;")
        layout.addWidget(label)

        self.size_groups_list = QListWidget()
        self.size_groups_list.currentItemChanged.connect(self.on_size_group_selected)
        layout.addWidget(self.size_groups_list)

        # Buttons for size group management
        btn_layout = QHBoxLayout()

        self.add_group_btn = QPushButton("Add")
        self.add_group_btn.clicked.connect(self.add_size_group)
        btn_layout.addWidget(self.add_group_btn)

        self.remove_group_btn = QPushButton("Remove")
        self.remove_group_btn.clicked.connect(self.remove_size_group)
        btn_layout.addWidget(self.remove_group_btn)

        self.rename_group_btn = QPushButton("Rename")
        self.rename_group_btn.clicked.connect(self.rename_size_group)
        btn_layout.addWidget(self.rename_group_btn)

        layout.addLayout(btn_layout)
        panel.setLayout(layout)
        return panel

    def create_sizes_panel(self):
        """Create right panel with sizes for selected group."""
        panel = QWidget()
        layout = QVBoxLayout()

        self.sizes_label = QLabel("Sizes in Group:")
        self.sizes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.sizes_label)

        self.sizes_list = QListWidget()
        layout.addWidget(self.sizes_list)

        # First row of buttons for size management
        btn_layout = QHBoxLayout()

        self.add_size_btn = QPushButton("Add Size")
        self.add_size_btn.clicked.connect(self.add_size_to_group)
        btn_layout.addWidget(self.add_size_btn)

        self.remove_size_btn = QPushButton("Remove")
        self.remove_size_btn.clicked.connect(self.remove_size_from_group)
        btn_layout.addWidget(self.remove_size_btn)

        self.edit_alias_btn = QPushButton("Edit Alias")
        self.edit_alias_btn.clicked.connect(self.edit_size_alias)
        btn_layout.addWidget(self.edit_alias_btn)

        layout.addLayout(btn_layout)

        # Second row of buttons for color management
        color_btn_layout = QHBoxLayout()

        self.pick_color_btn = QPushButton("Pick Color")
        self.pick_color_btn.clicked.connect(self.pick_size_color)
        color_btn_layout.addWidget(self.pick_color_btn)

        self.random_color_btn = QPushButton("Random Color")
        self.random_color_btn.clicked.connect(self.randomize_size_color)
        color_btn_layout.addWidget(self.random_color_btn)

        color_btn_layout.addStretch()

        layout.addLayout(color_btn_layout)

        panel.setLayout(layout)
        return panel

    def load_size_groups(self):
        """Load size groups into the list."""
        self.size_groups_list.clear()
        for group_name in sorted(self.working_copy_size_groups.keys()):
            self.size_groups_list.addItem(group_name)

        # Select first item if available
        if self.size_groups_list.count() > 0:
            self.size_groups_list.setCurrentRow(0)

    def on_size_group_selected(self, current, _previous):
        """Handle size group selection - load sizes for this group."""
        if not current:
            self.sizes_list.clear()
            self.sizes_label.setText("Sizes in Group:")
            return

        group_name = current.text()
        self.sizes_label.setText(f"Sizes in Group \"{group_name}\":")
        self.load_sizes_for_group(group_name)

    def load_sizes_for_group(self, group_name: str):
        """Load sizes for the selected group with color indicators."""
        self.sizes_list.clear()

        if group_name not in self.working_copy_size_groups:
            return

        group_data = self.working_copy_size_groups[group_name]
        if isinstance(group_data, dict) and "sizes" in group_data:
            for size in group_data["sizes"]:
                size_ratio = size["ratio"]
                alias = size["alias"]
                # Get color from global settings (per size ratio, not per group)
                color = self.config.get_size_color(size_ratio) or "#4CAF50"
                # Calculate ratio for display
                try:
                    ratio = self.config.parse_size_ratio(size_ratio)
                    display_text = f"{alias} ({size_ratio}, ratio: {ratio:.2f})"
                except ValueError:
                    display_text = f"{alias} ({size_ratio}, invalid format)"

                item = QListWidgetItem(display_text)
                item.setForeground(QColor(color))
                self.sizes_list.addItem(item)

    def add_size_group(self):
        """Add a new size group."""
        name, ok = QInputDialog.getText(
            self, "Add Size Group", "Enter size group name:"
        )

        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "Invalid Name", "Size group name cannot be empty.")
                return

            if name in self.working_copy_size_groups:
                QMessageBox.warning(self, "Duplicate Name", f"Size group '{name}' already exists.")
                return

            self.working_copy_size_groups[name] = {"sizes": []}
            self.load_size_groups()

            # Select the newly added group
            items = self.size_groups_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.size_groups_list.setCurrentItem(items[0])

    def remove_size_group(self):
        """Remove the selected size group."""
        current_item = self.size_groups_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a size group to remove.")
            return

        group_name = current_item.text()

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete size group '{group_name}'?\n\n"
            "This will clear tags from any images using this group.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.working_copy_size_groups[group_name]
            self.load_size_groups()

    def rename_size_group(self):
        """Rename the selected size group."""
        current_item = self.size_groups_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a size group to rename.")
            return

        old_name = current_item.text()

        new_name, ok = QInputDialog.getText(
            self, "Rename Size Group", "Enter new name:", text=old_name
        )

        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "Invalid Name", "Size group name cannot be empty.")
                return

            if new_name == old_name:
                return  # No change

            if new_name in self.working_copy_size_groups:
                QMessageBox.warning(self, "Duplicate Name", f"Size group '{new_name}' already exists.")
                return

            # Rename the group
            self.working_copy_size_groups[new_name] = self.working_copy_size_groups.pop(old_name)
            self.load_size_groups()

            # Select the renamed group
            items = self.size_groups_list.findItems(new_name, Qt.MatchFlag.MatchExactly)
            if items:
                self.size_groups_list.setCurrentItem(items[0])

    def add_size_to_group(self):
        """Add a new size to the selected group."""
        current_item = self.size_groups_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a size group first.")
            return

        group_name = current_item.text()

        # Create custom dialog for adding size
        dialog = AddSizeDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            size_ratio, alias = dialog.get_size_data()

            # Check if size already exists in this group
            group_data = self.working_copy_size_groups[group_name]
            if "sizes" not in group_data:
                group_data["sizes"] = []

            for size in group_data["sizes"]:
                if size["ratio"] == size_ratio:
                    QMessageBox.warning(
                        self, "Duplicate Size",
                        f"Size '{size_ratio}' already exists in this group."
                    )
                    return

            # Auto-assign color if this is a new size ratio (color is global)
            if not self.config.get_size_color(size_ratio):
                self.config.set_size_color(size_ratio, generate_random_color())

            # Add the size (color is stored globally in settings, not here)
            group_data["sizes"].append({"ratio": size_ratio, "alias": alias})
            self.load_sizes_for_group(group_name)

    def remove_size_from_group(self):
        """Remove the selected size from the group."""
        current_group = self.size_groups_list.currentItem()
        current_size = self.sizes_list.currentItem()

        if not current_group or not current_size:
            QMessageBox.warning(self, "No Selection", "Please select a size to remove.")
            return

        group_name = current_group.text()
        size_text = current_size.text()

        # Extract size ratio from display text (format: "alias (size_ratio, ratio: X.XX)")
        size_ratio = self._extract_size_ratio_from_display(size_text)

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Remove size '{size_ratio}' from group '{group_name}'?\n\n"
            "This will clear tags from any images using this size in this group.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            group_data = self.working_copy_size_groups[group_name]
            if "sizes" in group_data:
                group_data["sizes"] = [s for s in group_data["sizes"] if s["ratio"] != size_ratio]
                self.load_sizes_for_group(group_name)

    def edit_size_alias(self):
        """Edit the alias of the selected size."""
        current_group = self.size_groups_list.currentItem()
        current_size = self.sizes_list.currentItem()

        if not current_group or not current_size:
            QMessageBox.warning(self, "No Selection", "Please select a size to edit.")
            return

        group_name = current_group.text()
        size_text = current_size.text()

        # Extract size ratio from display text
        size_ratio = self._extract_size_ratio_from_display(size_text)

        # Get current alias
        group_data = self.working_copy_size_groups[group_name]
        current_alias = size_ratio  # Default
        if "sizes" in group_data:
            for size in group_data["sizes"]:
                if size["ratio"] == size_ratio:
                    current_alias = size["alias"]
                    break

        new_alias, ok = QInputDialog.getText(
            self, "Edit Alias", f"Enter new alias for '{size_ratio}':", text=current_alias
        )

        if ok:
            new_alias = new_alias.strip() or size_ratio  # Default to ratio if empty

            # Update the alias
            if "sizes" in group_data:
                for size in group_data["sizes"]:
                    if size["ratio"] == size_ratio:
                        size["alias"] = new_alias
                        break

                self.load_sizes_for_group(group_name)

    def pick_size_color(self):
        """Open color dialog to pick a color for the selected size.
        Color is global per size ratio (same color across all groups)."""
        current_group = self.size_groups_list.currentItem()
        current_size = self.sizes_list.currentItem()

        if not current_group or not current_size:
            QMessageBox.warning(self, "No Selection", "Please select a size to change its color.")
            return

        group_name = current_group.text()
        size_text = current_size.text()
        size_ratio = self._extract_size_ratio_from_display(size_text)

        # Get current color from global settings
        current_color = self.config.get_size_color(size_ratio) or "#4CAF50"

        # Open color dialog
        color = QColorDialog.getColor(QColor(current_color), self, f"Pick Color for Size '{size_ratio}'")
        if color.isValid():
            new_color = color.name()
            # Update the color in global settings (applies to all groups with this size)
            self.config.set_size_color(size_ratio, new_color)
            self.load_sizes_for_group(group_name)

    def randomize_size_color(self):
        """Generate a random color for the selected size.
        Color is global per size ratio (same color across all groups)."""
        current_group = self.size_groups_list.currentItem()
        current_size = self.sizes_list.currentItem()

        if not current_group or not current_size:
            QMessageBox.warning(self, "No Selection", "Please select a size to randomize its color.")
            return

        group_name = current_group.text()
        size_text = current_size.text()
        size_ratio = self._extract_size_ratio_from_display(size_text)

        # Generate random color and update global settings
        new_color = generate_random_color()
        self.config.set_size_color(size_ratio, new_color)
        self.load_sizes_for_group(group_name)

    def _extract_size_ratio_from_display(self, display_text: str) -> str:
        """Extract size ratio from display text like 'alias (9x6, ratio: 1.50)'."""
        # Find text between '(' and ','
        start = display_text.find('(')
        end = display_text.find(',', start)
        if start != -1 and end != -1:
            return display_text[start + 1:end].strip()
        return ""

    def save_changes(self):
        """Save all changes back to config and files."""
        # Save workspace directory setting
        workspace_dir = self.workspace_input.text().strip()
        self.config.set_setting("workspace_directory", workspace_dir)

        # Save size costs
        for size_ratio, spinbox in self.cost_spinboxes.items():
            self.config.set_size_cost(size_ratio, spinbox.value())

        # Save screen calibration (pixels per unit)
        self.config.set_setting("pixels_per_unit", self.calibration_spinbox.value())

        # Save date stamp settings
        self.config.set_setting("date_stamp_physical_height", self.physical_height_spinbox.value())
        self.config.set_setting("date_stamp_format", self.format_input.text().strip())
        self.config.set_setting("date_stamp_position", self.position_combo.currentText())
        self.config.set_setting("date_stamp_temp_outer", self.outer_temp_slider.value())
        self.config.set_setting("date_stamp_temp_core", self.core_temp_slider.value())
        self.config.set_setting("date_stamp_glow_intensity", self.glow_spinbox.value())
        self.config.set_setting("date_stamp_margin", self.margin_spinbox.value())
        self.config.set_setting("date_stamp_opacity", self.opacity_spinbox.value())

        self.config.save_settings()

        # Calculate deletions
        deleted_size_groups = self.original_size_group_names - set(self.working_copy_size_groups.keys())

        # Calculate deleted size ratios (sizes removed from any group)
        deleted_size_ratios = set()
        for group_name in self.working_copy_size_groups.keys():
            if group_name in self.original_sizes_per_group:
                # Get current sizes in this group
                current_sizes = set()
                group_data = self.working_copy_size_groups[group_name]
                if isinstance(group_data, dict) and "sizes" in group_data:
                    current_sizes = {size["ratio"] for size in group_data["sizes"]}

                # Find sizes that were removed from this group
                removed_from_group = self.original_sizes_per_group[group_name] - current_sizes
                deleted_size_ratios.update(removed_from_group)

        # Save to config
        self.config.size_groups = self.working_copy_size_groups
        self.config.save_size_groups()

        # Clear tags from affected images
        if deleted_size_ratios or deleted_size_groups:
            self.project_manager.clear_tags_for_deleted_sizes(deleted_size_ratios, deleted_size_groups)

        QMessageBox.information(
            self, "Success",
            "Configuration saved successfully!\n\n"
            "The changes will take effect immediately."
        )

        self.accept()


class AddSizeDialog(QDialog):
    """Dialog for adding a new size to a group."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Add Size to Group")
        self.init_ui()

    def init_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout()

        # Size ratio input
        ratio_label = QLabel("Size Ratio (e.g., 9x6, 5x7):")
        layout.addWidget(ratio_label)

        self.size_ratio_input = QLineEdit()
        self.size_ratio_input.setPlaceholderText("NxM format")
        self.size_ratio_input.textChanged.connect(self.update_ratio_display)
        layout.addWidget(self.size_ratio_input)

        # Ratio display
        self.ratio_label = QLabel("Calculated Ratio: -")
        self.ratio_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.ratio_label)

        # Alias input
        alias_label = QLabel("User-Friendly Name (alias):")
        layout.addWidget(alias_label)

        self.alias_input = QLineEdit()
        self.alias_input.setPlaceholderText("e.g., Small Portrait")
        layout.addWidget(self.alias_input)

        # Info label
        info_label = QLabel("Note: Size ratio must follow NxM pattern (e.g., 9x6)\nColor is auto-assigned and can be changed later.")
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self.validate_and_accept)
        self.add_btn.setEnabled(False)  # Disabled until valid input
        btn_layout.addWidget(self.add_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def update_ratio_display(self, text):
        """Update the ratio display when size ratio changes."""
        if not text:
            self.ratio_label.setText("Calculated Ratio: -")
            self.ratio_label.setStyleSheet("color: gray; font-style: italic;")
            self.add_btn.setEnabled(False)
            return

        try:
            ratio = self.config.parse_size_ratio(text)
            self.ratio_label.setText(f"Calculated Ratio: {ratio:.2f}")
            self.ratio_label.setStyleSheet("color: green; font-style: italic;")
            self.add_btn.setEnabled(True)
        except ValueError as e:
            self.ratio_label.setText(f"Invalid format: {str(e)}")
            self.ratio_label.setStyleSheet("color: red; font-style: italic;")
            self.add_btn.setEnabled(False)

    def validate_and_accept(self):
        """Validate input and accept the dialog."""
        size_ratio = self.size_ratio_input.text().strip()
        alias = self.alias_input.text().strip()

        if not size_ratio:
            QMessageBox.warning(self, "Invalid Input", "Size ratio cannot be empty.")
            return

        if not self.config.validate_size_id(size_ratio):
            QMessageBox.warning(
                self, "Invalid Format",
                "Size ratio must follow NxM pattern (e.g., 9x6, 5x7)."
            )
            return

        # Default alias to size ratio if empty
        if not alias:
            alias = size_ratio

        self.accept()

    def get_size_data(self):
        """Get the entered size data."""
        size_ratio = self.size_ratio_input.text().strip()
        alias = self.alias_input.text().strip() or size_ratio
        return size_ratio, alias


class CalibrationLineWidget(QFrame):
    """Widget that displays a horizontal line for screen calibration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.length = 100  # Length in pixels
        self.setMinimumHeight(80)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setStyleSheet("background-color: white;")

    def set_length(self, length: int):
        """Set the length of the calibration line."""
        self.length = max(10, min(1000, length))
        self.update()

    def paintEvent(self, event):
        """Draw the calibration line."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate center position
        center_y = self.height() // 2
        start_x = (self.width() - self.length) // 2
        end_x = start_x + self.length

        # Draw the main line
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(start_x, center_y, end_x, center_y)

        # Draw end markers (small vertical lines)
        marker_height = 15
        painter.drawLine(start_x, center_y - marker_height, start_x, center_y + marker_height)
        painter.drawLine(end_x, center_y - marker_height, end_x, center_y + marker_height)

        # Draw middle marker
        mid_x = (start_x + end_x) // 2
        painter.drawLine(mid_x, center_y - marker_height // 2, mid_x, center_y + marker_height // 2)

        # Draw length label
        painter.setPen(QColor(100, 100, 100))
        label_text = f"{self.length} px = 1 unit"
        painter.drawText(start_x, center_y + 30, label_text)

        painter.end()
