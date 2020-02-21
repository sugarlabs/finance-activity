# Copyright 2008 by Wade Brainerd.
# This file is part of Finance.
#
# Finance is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Finance is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Finance.  If not, see <http://www.gnu.org/licenses/>.

# Import standard Python modules.
import time
import datetime
import locale
from gettext import gettext as _
import logging

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

from sugar3.graphics import style

# Import activity module
import colors
from extractinput import evaluate
from extractinput import _invalid_number_alert

REGISTER_HELP = _(
    'Welcome to Finance! This activity keeps track of income '
    'and expenses for anything that earns or spends money, like a school '
    'club.  To get started, use the Transaction box to add credits and '
    'debits.\nOnce you have entered some transactions, visit the Chart '
    'and Budget views to see more.')


class RegisterScreen(Gtk.VBox):
    def __init__(self, activity):
        GObject.GObject.__init__(self)

        self.activity = activity

        # Build the transaction list.
        self.treeview = Gtk.TreeView()
        self.treeview.set_rules_hint(True)
        self.treeview.set_enable_search(False)

        font_size = int(style.FONT_SIZE * 1.25)
        font = Pango.FontDescription("Sans %d" % font_size)
        self.treeview.modify_font(font)

        # Note that the only thing we store in our liststore is the
        # transaction id. All the actual data is in the activity
        # database.
        self.liststore = Gtk.ListStore(GObject.TYPE_INT)
        self.treeview.set_model(self.liststore)
        sep = style.DEFAULT_SPACING

        theme = b"* {-GtkTreeView-vertical-separator: %d;" \
                b"   -GtkTreeView-horizontal-separator: %d;}" % (sep, sep)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(theme)
        style_context = self.treeview.get_style_context()
        style_context.add_provider(css_provider,
                                   Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # Construct the columns.
        renderer = Gtk.CellRendererText()
        renderer.props.editable = True
        renderer.connect('editing-started', self.category_editing_started_cb)
        renderer.connect('edited', self.category_edit_cb)
        col = Gtk.TreeViewColumn(_('Category'), renderer)
        col.set_cell_data_func(renderer, self.category_render_cb)
        col.set_alignment(0.5)
        col.set_min_width(300)
        self.treeview.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.props.editable = True
        renderer.props.ellipsize = Pango.EllipsizeMode.END
        renderer.connect('editing-started',
                         self.description_editing_started_cb)
        renderer.connect('edited', self.description_edit_cb)
        col = Gtk.TreeViewColumn(_('Description'), renderer)
        col.set_cell_data_func(renderer, self.description_render_cb)
        col.set_expand(True)
        self.treeview.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.props.editable = True
        renderer.connect('edited', self.date_edit_cb)
        col = Gtk.TreeViewColumn(_('Date'), renderer)
        col.set_alignment(0.5)
        col.set_cell_data_func(renderer, self.date_render_cb)
        col.set_min_width(150)
        self.treeview.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.props.editable = True
        renderer.connect('edited', self.amount_edit_cb)
        col = Gtk.TreeViewColumn(_('Amount'), renderer)
        col.set_cell_data_func(renderer, self.amount_render_cb)
        col.set_alignment(0.5)
        col.set_min_width(120)
        renderer.props.xpad = style.DEFAULT_SPACING
        self.treeview.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.treeview)

        self.pack_start(scroll, True, True, 0)

    def build(self):
        # Build liststore.
        self.liststore.clear()
        for t in self.activity.visible_transactions:
            self.liststore.append((t['id'],))

    def description_render_cb(self, column, cell_renderer, model, iter, data):
        id = model.get_value(iter, 0)
        t = self.activity.transaction_map[id]
        cell_renderer.set_property('text', t['name'])
        self._set_font_color(t, cell_renderer)

    def description_editing_started_cb(self, cell_renderer, editable, path):
        completion = Gtk.EntryCompletion()
        completion.set_inline_completion(True)
        completion.set_popup_completion(True)
        completion.set_minimum_key_length(0)
        store = Gtk.ListStore(str)
        for c in list(self.activity.transaction_names.keys()):
            store.append([c])
        completion.set_model(store)
        completion.set_text_column(0)
        editable.set_completion(completion)
        editable.set_max_length(50)

    def description_edit_cb(self, cell_renderer, path, new_text):
        id = self.liststore[path][0]
        t = self.activity.transaction_map[id]
        t['name'] = new_text

        # Automatically fill in category if empty, and if transaction
        # name is known.
        if t['category'] == '' and new_text in self.activity.transaction_names:
            for ct in self.activity.data['transactions']:
                if ct['name'] == new_text and ct['category'] != '':
                    t['category'] = ct['category']

    def amount_render_cb(self, column, cell_renderer, model, iter, data):
        id = model.get_value(iter, 0)
        t = self.activity.transaction_map[id]
        cell_renderer.set_property('xalign', 1.0)
        self._set_font_color(t, cell_renderer)
        if t['type'] == 'credit':
            cell_renderer.set_property('text',
                                       locale.currency(t['amount'], False))
        else:
            cell_renderer.set_property('text',
                                       locale.currency(-t['amount'], False))

    def amount_edit_cb(self, cell_renderer, path, new_text):
        id = self.liststore[path][0]
        t = self.activity.transaction_map[id]
        try:
            t['amount'] = abs(locale.atof(new_text))
        except ValueError:
            if evaluate(new_text) is not None:
                t['amount'] = abs(locale.atof(evaluate(new_text)))
            else:
                _invalid_number_alert(self.activity)
        self.activity.update_summary()

    def date_render_cb(self, column, cell_renderer, model, iter, data):
        id = model.get_value(iter, 0)
        t = self.activity.transaction_map[id]
        when = datetime.date.fromordinal(t['date'])
        cell_renderer.set_property('text', when.isoformat())
        cell_renderer.set_property('xalign', 0.5)
        self._set_font_color(t, cell_renderer)

    def _set_font_color(self, t, cell_renderer):
        if t['type'] == 'credit':
            cell_renderer.set_property('foreground', colors.CREDIT_COLOR)
        else:
            cell_renderer.set_property('foreground', colors.DEBIT_COLOR)

    def date_edit_cb(self, cell_renderer, path, new_text):
        id = self.liststore[path][0]
        t = self.activity.transaction_map[id]
        when = time.strptime(new_text, "%Y-%m-%d")
        when = datetime.date(when[0], when[1], when[2])
        t['date'] = when.toordinal()
        self.activity.build_screen()

    def category_render_cb(self, column, cell_renderer, model, iter, data):
        id = model.get_value(iter, 0)
        t = self.activity.transaction_map[id]
        category = t['category']
        cell_renderer.set_property('text', category)
        if category:
            category_color = colors.get_category_color_str(category)
            cell_renderer.set_property('background', category_color)
            if not colors.is_too_light(category_color):
                cell_renderer.set_property('foreground', '#FFFFFF')
        else:
            cell_renderer.set_property('background', None)

    def category_editing_started_cb(self, cell_renderer, editable, path):
        completion = Gtk.EntryCompletion()
        completion.set_inline_completion(True)
        completion.set_popup_completion(True)
        completion.set_minimum_key_length(0)
        store = Gtk.ListStore(str)
        for c in list(self.activity.category_names.keys()):
            store.append([c])
        completion.set_model(store)
        completion.set_text_column(0)
        editable.set_completion(completion)
        editable.set_max_length(20)

    def category_edit_cb(self, cell_renderer, path, new_text):
        id = self.liststore[path][0]
        t = self.activity.transaction_map[id]
        t['category'] = new_text
        if new_text != '':
            self.activity.category_names[new_text] = 1

    def new_credit(self):
        id = self.activity.create_transaction(_('New Credit'), 'credit', 0)
        iter = self.liststore.append((id,))
        # Set cursor and begin editing the description.
        self.treeview.set_cursor(self.liststore.get_path(iter),
                                 self.treeview.get_column(0), True)

    def new_debit(self):
        id = self.activity.create_transaction(_('New Debit'), 'debit', 0)
        iter = self.liststore.append((id,))
        # Set cursor and begin editing the description.
        self.treeview.set_cursor(self.liststore.get_path(iter),
                                 self.treeview.get_column(0), True)

    def erase_item(self):
        sel = self.treeview.get_selection()
        logging.debug('erase item selection %s', sel)
        model, iterator = sel.get_selected()
        logging.debug('erase item %s', iterator)
        if iterator:
            id = model.get_value(iterator, 0)
            logging.debug('erase item id %s', id)
            self.activity.destroy_transaction(id)
            self.activity.update_summary()

            path = model.get_path(iterator)
            model.remove(iterator)

            # Select the next item, or else the last item.
            sel.select_path(path)
            if not sel.path_is_selected(path):
                row = path[0] - 1
                if row >= 0:
                    sel.select_path((row,))
