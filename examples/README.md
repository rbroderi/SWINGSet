# Win32 GUI examples

These examples mirror the organization and basic geometry of the
[Examples_Win32 Win32.Gui catalog](https://github.com/gammasoft71/Examples_Win32/tree/master/Win32.Gui).
They use only SWINGSet's public API and explicitly request the Win32 backend so
each program serves as a native-control visual check.

Runnable Python examples expose their backend-independent UI through either a
`build_toml() -> str` triple-quoted document or an adjacent same-stem `.toml`
file. Callback bodies and platform services remain registered in Python.

Run an example from the repository root:

```powershell
uv run python examples/Controls/button.py
uv run python examples/Applications/wordpad.py
```

Standalone procedural demos live at the root of this directory:

```powershell
uv run python examples/feature_showcase.py
uv run python examples/backend.py
uv run python examples/textual.py
uv run python examples/svg.py
```

## TOML interfaces

- [CustomerEditor](Toml/customer_editor.toml) with its
	[Python command handler](Toml/customer_editor.py)

## Hello worlds

- [HelloWorldEmoticons](HelloWorlds/hello_world_emoticons.py)
- [HelloWorldMessageBox](HelloWorlds/hello_world_message_box.py)
- [HelloWorldMessageBox2](HelloWorlds/hello_world_message_box_2.py)
- [HelloWorldPaint](HelloWorlds/hello_world_paint.py)
- [HelloWorldStaticText](HelloWorlds/hello_world_static_text.py)

## Applications

- [Application](Applications/application.py)
- [ApplicationIcon](Applications/application_icon.py)
- [ApplicationIdle](Applications/application_idle.py)
- [ClassicTheme](Applications/classic_theme.py)
- [WordPad](Applications/wordpad.py) combines menus, two toolbars, native
	dialogs, find/select, themes, font controls, rich selection formatting,
	status metrics, and portable `.swingdoc` persistence.

## Dialogs

- [AboutBox](Dialogs/about_box.py)
- [ColorDialog](Dialogs/color_dialog.py)
- [FindDialog](Dialogs/find_dialog.py)
- [FolderBrowserDialog](Dialogs/folder_browser_dialog.py)
- [FontDialog](Dialogs/font_dialog.py)
- [MessageBox](Dialogs/message_box.py)
- [MessageBox2](Dialogs/message_box_2.py)
- [OpenFileDialog](Dialogs/open_file_dialog.py)
- [PageSetupDialog](Dialogs/page_setup_dialog.py)
- [PrintDialog](Dialogs/print_dialog.py)
- [ReplaceDialog](Dialogs/replace_dialog.py)
- [SaveFileDialog](Dialogs/save_file_dialog.py)

## Windows

- [Window](Windows/window.py)
- [WindowVersionInfo](Windows/window_version_info.py)

## Menus and toolbars

- [MainMenu](MenusAndToolbars/main_menu.py)
- [Toolbar](MenusAndToolbars/toolbar.py)

## Layout managers

- [BorderLayout](Layouts/border_layout.py) uses five resizable directional regions.
- [BoxLayout](Layouts/box_layout.py) stacks controls along one non-wrapping axis.
- [CardLayout](Layouts/card_layout.py) switches between named pages.
- [FlowLayout](Layouts/flow_layout.py) arranges controls in wrapping rows.
- [GridBagLayout](Layouts/grid_bag_layout.py) builds a weighted, constrained form.
- [GridLayout](Layouts/grid_layout.py) divides space into equal cells.

## Containers

- [ColoredTabPages](Containers/colored_tab_pages.py)
- [GroupBox](Containers/group_box.py)
- [GroupBoxCheckBox](Containers/group_box_check_box.py)
- [GroupBoxRadioButton](Containers/group_box_radio_button.py)
- [Panel](Containers/panel.py)
- [TabControl](Containers/tab_control.py)
- [TabControl2](Containers/tab_control_2.py)

## Controls

- [Button](Controls/button.py)
- [CheckBox](Controls/check_box.py)
- [ComboBox](Controls/combo_box.py)
- [KeyEvents](Controls/key_events.py)
- [MouseEvents](Controls/mouse_events.py)
- [PasswordField](Controls/password_field.py)
- [ProgressBar](Controls/progress_bar.py)
- [RadioButton](Controls/radio_button.py)
- [RichTextPane](Controls/rich_text_pane.py)
- [ScrollPane](Controls/scroll_pane.py)
- [Separator](Controls/separator.py)
- [Spinner](Controls/spinner.py)
- [StaticText](Controls/static_text.py)
- [StaticPicture](Controls/static_picture.py)
- [StaticPictureResource](Controls/static_picture_resource.py)
- [TextBox](Controls/text_box.py)
- [TrackBar](Controls/track_bar.py)
- [ToolTip](Controls/tool_tip.py)

## Components

- [Timer](Components/timer.py)

## Styling

- [ComponentColors](Styling/component_colors.py)
- [CommonMarkText](Styling/commonmark_text.py)
- [TomlStyleCascade](Styling/toml_style_cascade.py)

The catalog now includes specialized common dialogs, application events,
bitmap resources, colored tab pages, Windows version-resource inspection,
scrolling, rich text, password input, spinners, separators, and tooltips.