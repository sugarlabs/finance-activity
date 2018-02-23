from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from sugar3.graphics import style
from sugar3.graphics.palette import Palette
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palette import ToolInvoker
from sugar3.graphics.icon import Icon


class FilterToolItem(Gtk.ToolButton):

    _LABEL_MAX_WIDTH = 18
    _MAXIMUM_PALETTE_COLUMNS = 4

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_LAST, None, ([str])), }

    def __init__(self, default_icon, default_value, options, palette_title):
        self._palette_invoker = ToolInvoker()
        self._options = options
        self._palette_title = palette_title
        Gtk.ToolButton.__init__(self)
        self._value = default_value
        self._label = self._options[default_value]
        self.set_is_important(True)
        self.set_size_request(style.GRID_CELL_SIZE, -1)

        self._label_widget = Gtk.Label()
        self._label_widget.set_alignment(0.0, 0.5)
        self._label_widget.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self._label_widget.set_max_width_chars(self._LABEL_MAX_WIDTH)
        self._label_widget.set_use_markup(True)
        self._label_widget.set_markup(self._label)
        self.set_label_widget(self._label_widget)
        self._label_widget.show()

        self.set_widget_icon(icon_name=default_icon)

        self._hide_tooltip_on_click = True
        self._palette_invoker.attach_tool(self)
        self._palette_invoker.props.toggle_palette = True
        self._palette_invoker.props.lock_palette = True

        self.palette = Palette(self._palette_title)
        self.palette.set_invoker(self._palette_invoker)

        self.props.palette.set_content(self.set_palette_list(options))

    def set_options(self, options):
        self._options = options
        self.palette = Palette(self._palette_title)
        self.palette.set_invoker(self._palette_invoker)
        self.props.palette.set_content(self.set_palette_list(options))
        if self._value not in self._options.keys():
            new_value = self._options.keys()[0]
            self._value = new_value
            self._set_widget_label(self._options[new_value])
            self.emit('changed', new_value)

    def set_widget_icon(self, icon_name=None):
        icon = Icon(icon_name=icon_name,
                    pixel_size=style.SMALL_ICON_SIZE)
        self.set_icon_widget(icon)
        icon.show()

    def _set_widget_label(self, label=None):
        # FIXME: Ellipsis is not working on these labels.
        if label is None:
            label = self._label
        if len(label) > self._LABEL_MAX_WIDTH:
            label = label[0:7] + '...' + label[-7:]
        self._label_widget.set_markup(label)
        self._label = label

    def __destroy_cb(self, icon):
        if self._palette_invoker is not None:
            self._palette_invoker.detach()

    def create_palette(self):
        return None

    def get_palette(self):
        return self._palette_invoker.palette

    def set_palette(self, palette):
        self._palette_invoker.palette = palette

    palette = GObject.property(
        type=object, setter=set_palette, getter=get_palette)

    def get_palette_invoker(self):
        return self._palette_invoker

    def set_palette_invoker(self, palette_invoker):
        self._palette_invoker.detach()
        self._palette_invoker = palette_invoker

    palette_invoker = GObject.property(
        type=object, setter=set_palette_invoker, getter=get_palette_invoker)

    def do_draw(self, cr):
        if self.palette and self.palette.is_up():
            allocation = self.get_allocation()
            # draw a black background, has been done by the engine before
            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.paint()

        Gtk.ToolButton.do_draw(self, cr)

        if self.palette and self.palette.is_up():
            invoker = self.palette.props.invoker
            invoker.draw_rectangle(cr, self.palette)

        return False

    def set_palette_list(self, options):
        _menu_item = PaletteMenuItem(text_label=options[options.keys()[0]])
        req2 = _menu_item.get_preferred_size()[1]
        menuitem_width = req2.width
        menuitem_height = req2.height

        palette_width = Gdk.Screen.width() - style.GRID_CELL_SIZE
        palette_height = Gdk.Screen.height() - style.GRID_CELL_SIZE * 3

        nx = min(self._MAXIMUM_PALETTE_COLUMNS,
                 int(palette_width / menuitem_width))
        ny = min(int(palette_height / menuitem_height), len(options) + 1)
        if ny >= len(options):
            nx = 1
            ny = len(options)

        grid = Gtk.Grid()
        grid.set_row_spacing(style.DEFAULT_PADDING)
        grid.set_column_spacing(0)
        grid.set_border_width(0)
        grid.show()

        x = 0
        y = 0

        for key in sorted(options):
            menu_item = PaletteMenuItem()
            menu_item.set_label(options[key])

            menu_item.set_size_request(style.GRID_CELL_SIZE * 3, -1)

            menu_item.connect('button-release-event', self._option_selected,
                              key)
            grid.attach(menu_item, x, y, 1, 1)
            x += 1
            if x == nx:
                x = 0
                y += 1

            menu_item.show()

        if palette_height < (y * menuitem_height + style.GRID_CELL_SIZE):
            # if the grid is bigger than the palette, put in a scrolledwindow
            scrolled_window = Gtk.ScrolledWindow()
            scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                       Gtk.PolicyType.AUTOMATIC)
            scrolled_window.set_size_request(nx * menuitem_width,
                                             (ny + 1) * menuitem_height)
            scrolled_window.add_with_viewport(grid)
            return scrolled_window
        else:
            return grid

    def _option_selected(self, menu_item, event, key):
        self._set_widget_label(self._options[key])
        self._value = key
        self.emit('changed', key)
