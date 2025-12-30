import copy
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel, QLineEdit, QMessageBox, QInputDialog, QSplitter, QWidget,
    QFileDialog, QGroupBox
)
from PyQt6.QtCore import Qt


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
        self.init_ui()

    def init_ui(self):
        """Create the split-panel interface."""
        main_layout = QVBoxLayout()

        # Add workspace directory section at the top
        workspace_section = self.create_workspace_section()
        main_layout.addWidget(workspace_section)

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

        main_layout.addWidget(splitter)

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

    def create_workspace_section(self):
        """Create workspace directory configuration section."""
        group_box = QGroupBox("Workspace Settings")
        layout = QHBoxLayout()

        label = QLabel("Workspace Directory:")
        layout.addWidget(label)

        # Get current workspace directory from settings
        current_workspace = self.config.get_setting("workspace_directory", "")
        self.workspace_input = QLineEdit()
        self.workspace_input.setText(current_workspace)
        self.workspace_input.setPlaceholderText("Select a folder for storing projects")
        layout.addWidget(self.workspace_input)

        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_workspace_directory)
        layout.addWidget(browse_btn)

        group_box.setLayout(layout)
        return group_box

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

        # Buttons for size management
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

    def on_size_group_selected(self, current, previous):
        """Handle size group selection - load sizes for this group."""
        if not current:
            self.sizes_list.clear()
            self.sizes_label.setText("Sizes in Group:")
            return

        group_name = current.text()
        self.sizes_label.setText(f"Sizes in Group \"{group_name}\":")
        self.load_sizes_for_group(group_name)

    def load_sizes_for_group(self, group_name: str):
        """Load sizes for the selected group."""
        self.sizes_list.clear()

        if group_name not in self.working_copy_size_groups:
            return

        group_data = self.working_copy_size_groups[group_name]
        if isinstance(group_data, dict) and "sizes" in group_data:
            for size in group_data["sizes"]:
                size_ratio = size["ratio"]
                alias = size["alias"]
                # Calculate ratio for display
                try:
                    ratio = self.config.parse_size_ratio(size_ratio)
                    display_text = f"{alias} ({size_ratio}, ratio: {ratio:.2f})"
                except ValueError:
                    display_text = f"{alias} ({size_ratio}, invalid format)"

                self.sizes_list.addItem(display_text)

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

            # Add the size
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
        info_label = QLabel("Note: Size ratio must follow NxM pattern (e.g., 9x6)")
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
