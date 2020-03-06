#!/usr/bin/env python
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

"""Finance - Home financial software for the OLPC XO."""

# Import standard Python modules.
import os
import logging
import datetime
import locale
from gettext import gettext as _
import json
import tempfile
import io
import dbus
import copy

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk
from gi.repository import Pango

# Import Sugar UI modules.
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.graphics import style

from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import RedoButton
from sugar3.activity.widgets import UndoButton
from sugar3.activity import activity
from sugar3.datastore import datastore
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon
from sugar3.graphics.palettemenu import PaletteMenuItem
from sugar3.graphics.palettemenu import PaletteMenuBox
from sugar3 import profile

# Import screen classes.
import registerscreen
import chartscreen
import budgetscreen
from helpbutton import HelpButton
import colors
from filtertoolitem import FilterToolItem
import emptypanel

# Set up localization.
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:  # doesn't matter if $LANG invalid
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')

# Initialize logging.
log = logging.getLogger('Finance')
log.setLevel(logging.DEBUG)
logging.basicConfig()

DAY = 0
WEEK = 1
MONTH = 2
YEAR = 3
FOREVER = 4


# This is the main Finance activity class.
#
# It owns the main application window, and all the various toolbars
# and options. Screens are stored in a stack, with the currently
# active screen on top.

class Finance(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title(_("Finance"))
        self.max_participants = 1

        # Initialize database.
        # data
        #   next_id
        #   transactions
        #     id, name, type, amount, date, category
        #   budgets
        #     category, period, amount, budget
        self.data = {
            'next_id': 0,
            'transactions': [],
            'budgets': {}
        }

        self.transaction_map = {}
        self.visible_transactions = []

        self.undo_transaction_map = []
        self.undo_data_map = []

        self.redo_id_map = []
        self.redo_transaction_map = []

        self.transaction_names = {}
        self.category_names = {}

        # Initialize view period to the first of the month.
        self.period = MONTH
        self.period_start = self.get_this_period()

        # Create screens.
        self.register = registerscreen.RegisterScreen(self)
        self.chart = chartscreen.ChartScreen(self)
        self.budget = budgetscreen.BudgetScreen(self)

        self.build_toolbox()

        self.screenbox = Gtk.VBox()

        self.headerbox = self.build_header()
        self._active_panel = None

        # Add the summary data.

        self.startlabel = Gtk.Label()
        self.startamountlabel = Gtk.Label()
        self.creditslabel = Gtk.Label()
        self.debitslabel = Gtk.Label()
        self.balancelabel = Gtk.Label()
        self.balancelabel.props.margin_left = style.DEFAULT_SPACING
        self.balancelabel.props.margin_right = style.DEFAULT_SPACING

        font_size = int(style.FONT_SIZE * 1.25)
        font = Pango.FontDescription("Sans %d" % font_size)
        for label in (self.startlabel, self.startamountlabel,
                      self.creditslabel, self.debitslabel):
            label.modify_font(font)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.START)
            label.props.margin = style.DEFAULT_PADDING

        self.balance_evbox = Gtk.EventBox()
        self.balance_evbox.add(self.balancelabel)
        summarybox = Gtk.Grid()
        summarybox.attach(self.startlabel, 0, 0, 1, 1)
        summarybox.attach(self.startamountlabel, 0, 1, 1, 1)
        summarybox.attach(self.creditslabel, 1, 0, 1, 1)
        summarybox.attach(self.debitslabel, 1, 1, 1, 1)
        summarybox.attach(self.balance_evbox, 2, 0, 1, 2)
        self.balance_evbox.set_halign(Gtk.Align.END)

        summary_evbox = Gtk.EventBox()
        summary_evbox.add(summarybox)
        summary_evbox.modify_bg(Gtk.StateType.NORMAL,
                                style.Color('#666666').get_gdk_color())
        summary_evbox.set_size_request(-1, style.GRID_CELL_SIZE)

        vbox = Gtk.VBox()

        vbox.pack_start(self.headerbox, False, False, 0)
        vbox.pack_start(self.screenbox, True, True, 0)
        vbox.pack_start(summary_evbox, False, False, 0)

        # Start with the empty screen.
        self.empty_panel = emptypanel.create_empty_panel(
            'row-insert-credit',
            _('Add some credit or debit to get started!'),
            _('Add credit'), self.__empty_panel_btn_cb)

        self._set_internal_panel(self.empty_panel)

        # This has to happen last, because it calls the read_file
        # method when restoring from the Journal.
        self.set_canvas(vbox)

        self.show_all()
        self.show_header_controls()

        if os.getenv('FINANCE_TEST'):
            self.create_test_data()
            self._set_internal_panel(self.register)

    def build_toolbox(self):

        view_tool_group = None
        registerbtn = RadioToolButton()
        registerbtn.props.icon_name = 'view-list'
        registerbtn.props.label = _('Register')
        registerbtn.set_tooltip(_("Register"))
        registerbtn.props.group = view_tool_group
        view_tool_group = registerbtn
        registerbtn.props.accelerator = '<Ctrl>1'
        registerbtn.connect('clicked', self.register_cb)

        budgetbtn = RadioToolButton()
        budgetbtn.props.icon_name = 'budget'
        budgetbtn.props.label = _('Budget')
        budgetbtn.set_tooltip(_("Budget"))
        budgetbtn.props.group = view_tool_group
        budgetbtn.props.accelerator = '<Ctrl>2'
        budgetbtn.connect('clicked', self.budget_cb)

        chartbtn = RadioToolButton()
        chartbtn.props.icon_name = 'chart'
        chartbtn.props.label = _('Chart')
        chartbtn.set_tooltip(_("Chart"))
        chartbtn.props.group = view_tool_group
        chartbtn.props.accelerator = '<Ctrl>3'
        chartbtn.connect('clicked', self.chart_cb)

        helpbutton = self._create_help_button()
        helpbutton.show_all()

        self.toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.toolbar_box.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        self.toolbar_box.toolbar.insert(registerbtn, -1)
        self.toolbar_box.toolbar.insert(budgetbtn, -1)
        self.toolbar_box.toolbar.insert(chartbtn, -1)

        self.toolbar_box.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        self.toolbar_box.toolbar.insert(helpbutton, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)

        self.toolbar_box.toolbar.insert(StopButton(self), -1)
        self.set_toolbar_box(self.toolbar_box)

        activity_button.page.insert(self._create_export_button(), -1)

        self.toolbar_box.show_all()

    def _create_export_button(self):
        # Add expoprt button
        export_data = ToolButton('save-as-data')

        export_data.props.tooltip = _('Export data')
        export_data.props.hide_tooltip_on_click = False
        export_data.palette_invoker.props.toggle_palette = True
        export_data.show()

        menu_box = PaletteMenuBox()
        export_data.props.palette.set_content(menu_box)

        menu_item = PaletteMenuItem(text_label=_('Export credits by day'))
        menu_item.connect('activate', self.__export_data_to_chart_cb,
                          'credit', DAY)
        menu_box.append_item(menu_item)

        menu_item = PaletteMenuItem(text_label=_('Export debits by day'))
        menu_item.connect('activate', self.__export_data_to_chart_cb,
                          'debit', DAY)
        menu_box.append_item(menu_item)

        menu_item = PaletteMenuItem(text_label=_('Export credits by month'))
        menu_item.connect('activate', self.__export_data_to_chart_cb,
                          'credit', MONTH)
        menu_box.append_item(menu_item)

        menu_item = PaletteMenuItem(text_label=_('Export debits by month'))
        menu_item.connect('activate', self.__export_data_to_chart_cb,
                          'debit', MONTH)
        menu_box.append_item(menu_item)

        menu_box.show_all()
        return export_data

    def _create_help_button(self):
        helpitem = HelpButton()
        helpitem.add_section(_('Register'), icon='view-list')
        helpitem.add_paragraph(registerscreen.REGISTER_HELP)
        helpitem.add_section(_('Budget'), icon='budget')
        helpitem.add_paragraph(budgetscreen.BUDGET_HELP)
        helpitem.add_section(_('Chart'), icon='chart')
        helpitem.add_paragraph(chartscreen.CHART_HELP)
        return helpitem

    def build_header(self):
        # Add the header.
        self.periodlabel = Gtk.Label()
        self.periodlabel.set_padding(10, 0)
        self._period_label_item = Gtk.ToolItem()
        self._period_label_item.add(self.periodlabel)
        self.periodlabel.set_halign(Gtk.Align.END)
        self._period_label_item.set_size_request(style.GRID_CELL_SIZE * 5, -1)

        headerbox = Gtk.Toolbar()
        headerbox.modify_bg(Gtk.StateType.NORMAL,
                            style.Color('#424242').get_gdk_color())
        headerbox.set_size_request(-1, style.GRID_CELL_SIZE)

        # register buttons
        self.newcreditbtn = ToolButton('row-insert-credit')
        self.newcreditbtn.set_tooltip(_("New Credit"))
        self.newcreditbtn.props.accelerator = '<Ctrl>A'
        self.newcreditbtn.connect('clicked', self.__newcredit_cb)

        self.newdebitbtn = ToolButton('row-insert-debit')
        self.newdebitbtn.set_tooltip(_("New Debit"))
        self.newdebitbtn.props.accelerator = '<Ctrl>D'
        self.newdebitbtn.connect('clicked', self.__newdebit_cb)

        self.undoactionbtn = UndoButton()
        self.undoactionbtn.connect('clicked', self.__undoaction_cb)

        self.redoactionbtn = RedoButton()
        self.redoactionbtn.connect('clicked', self.__redoaction_cb)

        self.eraseitembtn = ToolButton('basket')
        self.eraseitembtn.set_tooltip(_("Erase Transaction"))
        self.eraseitembtn.props.accelerator = '<Ctrl>E'
        self.eraseitembtn.connect('clicked', self.__eraseitem_cb)

        headerbox.insert(self.newcreditbtn, -1)
        headerbox.insert(self.newdebitbtn, -1)
        headerbox.insert(self.eraseitembtn, -1)
        headerbox.insert(self.undoactionbtn, -1)
        headerbox.insert(self.redoactionbtn, -1)

        self.header_separator_visible = Gtk.SeparatorToolItem()
        headerbox.insert(self.header_separator_visible, -1)

        self.export_image = ToolButton('save-as-image')
        self.export_image.set_tooltip(_("Save as Image"))
        self.export_image.connect('clicked', self.__save_image_cb)
        headerbox.insert(self.export_image, -1)

        self._header_separator = Gtk.SeparatorToolItem()
        self._header_separator.props.draw = False
        self._header_separator.set_expand(True)
        headerbox.insert(self._header_separator, -1)

        # period controls
        self.thisperiodbtn = ToolButton('go-down')
        self.thisperiodbtn.props.accelerator = '<Ctrl>Down'
        self.thisperiodbtn.connect('clicked', self.thisperiod_cb)

        self.prevperiodbtn = ToolButton('go-previous-paired')
        self.prevperiodbtn.props.accelerator = '<Ctrl>Left'
        self.prevperiodbtn.connect('clicked', self.prevperiod_cb)

        self.nextperiodbtn = ToolButton('go-next-paired')
        self.nextperiodbtn.props.accelerator = '<Ctrl>Right'
        self.nextperiodbtn.connect('clicked', self.nextperiod_cb)

        period_options = {DAY: _('Day'), WEEK: _('Week'), MONTH: _('Month'),
                          YEAR: _('Year'), FOREVER: _('Forever')}
        periodcombo = FilterToolItem('calendar', MONTH, period_options,
                                     _('Select period'))

        periodcombo.connect('changed', self.__period_changed_cb)

        headerbox.insert(periodcombo, -1)
        headerbox.insert(self.prevperiodbtn, -1)
        headerbox.insert(self.nextperiodbtn, -1)
        headerbox.insert(self.thisperiodbtn, -1)

        headerbox.insert(self._period_label_item, -1)
        return headerbox

    def show_header_controls(self):
        for child in self.headerbox.get_children():
            child.show()
            if self._active_panel in (self.register, self.empty_panel):
                if child in (self.header_separator_visible,
                             self.export_image):
                    child.hide()
            elif self._active_panel == self.budget:
                if child in (self.newcreditbtn, self.newdebitbtn,
                             self.eraseitembtn, self.undoactionbtn,
                             self.redoactionbtn, self.header_separator_visible,
                             self.export_image):
                    child.hide()
            elif self._active_panel == self.chart:
                # Use NOT here
                if child not in (self.newcreditbtn, self.newdebitbtn,
                                 self.header_separator_visible,
                                 self.export_image):
                    child.hide()

    def register_cb(self, widget):
        self._set_internal_panel(self.register)
        self.show_header_controls()
        self.newcreditbtn.set_tooltip(_("New Credit"))
        self.newdebitbtn.set_tooltip(_("New Debit"))

    def budget_cb(self, widget):
        self._set_internal_panel(self.budget)
        self.show_header_controls()

    def chart_cb(self, widget):
        self._set_internal_panel(self.chart)
        self.show_header_controls()
        self.newcreditbtn.set_tooltip(_("Show Credits"))
        self.newdebitbtn.set_tooltip(_("Show Debits"))

    def _set_internal_panel(self, widget):
        if self.screenbox.get_children():
            self.screenbox.remove(self.screenbox.get_children()[0])
        self.screenbox.pack_start(widget, True, True, 0)
        widget.show_all()
        self._active_panel = widget
        self.build_screen()

    def build_screen(self):
        self.build_visible_transactions()

        if hasattr(self._active_panel, 'build'):
            self._active_panel.build()

        self.update_header()
        self.update_summary()
        self.update_toolbar()

    def __empty_panel_btn_cb(self, button):
        self._set_internal_panel(self.register)
        self.register.new_credit()

    def __newcredit_cb(self, widget):
        if self._active_panel == self.chart:
            # in the case of chart, select the graphic
            self.chart.set_mode(self.chart.CHART_CREDIT)
            return

        # this check is used when the emptypanel is visible
        if self._active_panel != self.register:
            self._set_internal_panel(self.register)
        self.register.new_credit()

    def __newdebit_cb(self, widget):
        if self._active_panel == self.chart:
            # in the case of chart, select the graphic
            self.chart.set_mode(self.chart.CHART_DEBIT)
            return

        # this check is used when the emptypanel is visible
        if self._active_panel != self.register:
            self._set_internal_panel(self.register)
        self.register.new_debit()

    def __undoaction_cb(self, widget):
        self.undo_transaction()
        self.build_screen()

    def __redoaction_cb(self, widget):
        self.redo_transaction()
        self.build_screen()

    def __eraseitem_cb(self, widget):
        self.register.erase_item()
        self.build_screen()

    def update_header(self):
        if self.period == DAY:
            # TRANS: representation of the "Day" period
            text = self.period_start.strftime(_("%B %d, %Y"))

        elif self.period == WEEK:
            # TRANS: representation of the "Week of" period
            text = _('Week of') + self.period_start.strftime(_(" %B %d, %Y"))

        elif self.period == MONTH:
            # TRANS: representation of the "Month" period
            text = self.period_start.strftime(_("%B, %Y"))

        elif self.period == YEAR:
            # TRANS: representation of the "Year" period
            text = self.period_start.strftime(_("%Y"))

        elif self.period == FOREVER:
            text = _('Forever')

        self.periodlabel.set_markup(
            "<span size='xx-large' color='white'><b>" + text + "</b></span>")

    def update_summary(self):
        # Calculate starting balance.
        start = 0.0
        for t in self.data['transactions']:
            d = t['date']
            if d < self.period_start.toordinal():
                if t['type'] == 'credit':
                    start += t['amount']
                else:
                    start -= t['amount']

        # Calculate totals for this period.
        credit_count = 0
        credit_total = 0.0
        debit_count = 0
        debit_total = 0.0
        total = start
        for t in self.visible_transactions:
            if t['type'] == 'credit':
                credit_count += 1
                credit_total += t['amount']
                total += t['amount']
            else:
                debit_count += 1
                debit_total += t['amount']
                total -= t['amount']

        # Update Balance.
        if total >= 0.0:
            balancecolor = colors.CREDIT_COLOR
        else:
            balancecolor = colors.DEBIT_COLOR
        balance = \
            "<span size='xx-large' foreground='white'><b>%s %s</b></span>" % \
            (_('Balance: '), locale.currency(total))
        self.balancelabel.set_markup(balance)

        self.balance_evbox.modify_bg(
            Gtk.StateType.NORMAL, style.Color(balancecolor).get_gdk_color())

        self.startlabel.set_markup(
            "<span foreground='white'><b>%s</b></span>" %
            _('Starting Balance:'))
        self.startamountlabel.set_markup(
            "<span foreground='white'><b>%s</b></span>" %
            locale.currency(start))

        self.creditslabel.set_markup(
            "<span foreground='white'><b>%s</b></span>" %
            (_('%(credit_total)s in %(credit_count)d credits') %
             {'credit_total': locale.currency(credit_total),
              'credit_count': credit_count}))

        self.debitslabel.set_markup(
            "<span foreground='white'><b>%s</b></span>" %
            (_('%(debit_total)s in %(debit_count)d debits') %
             {'debit_total': locale.currency(debit_total),
              'debit_count': debit_count}))

    def update_toolbar(self):
        # Disable the navigation when Forever is selected.
        next_prev = self.period != FOREVER
        self.prevperiodbtn.set_sensitive(next_prev)
        self.thisperiodbtn.set_sensitive(next_prev)
        self.nextperiodbtn.set_sensitive(next_prev)

        # This is a HACK to translate the string properly
        # http://bugs.sugarlabs.org/ticket/3190
        if self.period == MONTH:
            text_previous_period = _('Previous Month')
            text_this_period = _('This Month')
            text_next_period = _('Next Month')
        elif self.period == WEEK:
            text_previous_period = _('Previous Week')
            text_this_period = _('This Week')
            text_next_period = _('Next Week')
        elif self.period == DAY:
            text_previous_period = _('Previous Day')
            text_this_period = _('This Day')
            text_next_period = _('Next Day')
        elif self.period == YEAR:
            text_previous_period = _('Previous Year')
            text_this_period = _('This Year')
            text_next_period = _('Next Year')

        if self.period != FOREVER:
            self.prevperiodbtn.set_tooltip(text_previous_period)
            self.thisperiodbtn.set_tooltip(text_this_period)
            self.nextperiodbtn.set_tooltip(text_next_period)

    # Update the label self.period to reflect the period.
    def get_this_period(self):
        today = datetime.date.today()

        if self.period == DAY:
            return today

        elif self.period == WEEK:
            while today.weekday() != 0:
                today -= datetime.timedelta(days=1)
            return today

        elif self.period == MONTH:
            return datetime.date(today.year, today.month, 1)

        elif self.period == YEAR:
            return datetime.date(today.year, 1, 1)

        elif self.period == FOREVER:
            return datetime.date(1900, 1, 1)

    def get_next_period(self, start):
        if self.period == DAY:
            return start + datetime.timedelta(days=1)

        elif self.period == WEEK:
            return start + datetime.timedelta(days=7)

        elif self.period == MONTH:
            if start.month == 12:
                return datetime.date(start.year + 1, 1, 1)
            else:
                return datetime.date(start.year, start.month + 1, 1)

        elif self.period == YEAR:
            return datetime.date(start.year + 1, 1, 1)

    def get_prev_period(self, start):
        if self.period == DAY:
            return start - datetime.timedelta(days=1)

        elif self.period == WEEK:
            return start - datetime.timedelta(days=7)

        elif self.period == MONTH:
            if start.month == 1:
                return datetime.date(start.year - 1, 12, 1)
            else:
                return datetime.date(start.year, start.month - 1, 1)

        elif self.period == YEAR:
            return datetime.date(start.year - 1, 1, 1)

    def thisperiod_cb(self, widget):
        if self.period != FOREVER:
            self.period_start = self.get_this_period()
            self.build_screen()

    def nextperiod_cb(self, widget):
        if self.period != FOREVER:
            self.period_start = self.get_next_period(self.period_start)
            self.build_screen()

    def prevperiod_cb(self, widget):
        if self.period != FOREVER:
            self.period_start = self.get_prev_period(self.period_start)
            self.build_screen()

    def __period_changed_cb(self, widget, value):
        self.period = int(value)
        self.update_toolbar()

        # Jump to 'this period'.
        self.period_start = self.get_this_period()
        self.build_screen()

    def build_visible_transactions(self):
        if self.period == FOREVER:
            self.visible_transactions = self.data['transactions']

        else:
            period_start_ord = self.period_start.toordinal()
            period_end_ord = self.get_next_period(
                self.period_start).toordinal()

            self.visible_transactions = []
            for t in self.data['transactions']:
                d = t['date']
                if d >= period_start_ord and d < period_end_ord:
                    self.visible_transactions.append(t)

        self.visible_transactions.sort(key=lambda a: a['date'])

    def build_transaction_map(self):
        self.transaction_map = {}
        for t in self.data['transactions']:
            self.transaction_map[t['id']] = t

    def create_transaction(self, name='', type='debit', amount=0,
                           category='', date=datetime.date.today()):
        id = self.data['next_id']
        self.data['next_id'] += 1

        t = {
            'id': id,
            'name': name,
            'type': type,
            'amount': amount,
            'date': date.toordinal(),
            'category': category
        }
        self.data['transactions'].append(t)
        self.transaction_map[id] = t

        self.build_visible_transactions()

        return id

    def destroy_transaction(self, id):
        t = self.transaction_map[id]
        self.data['transactions'].remove(t)
        del self.transaction_map[id]

    def undo_transaction(self):
        if len(self.undo_transaction_map) == 0:
            return

        # print("undo id {}".format(self.undo_id_map))
        # print("undo trans {}".format(self.undo_transaction_map))
        print("undo data {}".format(self.undo_data_map))
        print("real data {}".format(self.data))

        # print("redo id {}".format(self.redo_id_map))
        # print("redo trans {}".format(self.redo_transaction_map))

        new_map = self.undo_transaction_map.pop()
        new_data = self.undo_data_map.pop()

        # self.redo_id_map.append(id)
        # self.redo_transaction_map.append(t.copy())

        # self.transaction_map = new_map.copy()
        self.data = copy.deepcopy(new_data)

        # self.build_transaction_map()
        self.build_visible_transactions()
        # self.update_summary()

    def redo_transaction(self):
        if len(self.redo_id_map) == 0:
            return

        # print("undo id {}".format(self.undo_id_map))
        # print("undo trans {}".format(self.undo_transaction_map))
        #
        # print("redo id {}".format(self.redo_id_map))
        # print("redo trans {}".format(self.redo_transaction_map))
        #
        # id = self.redo_id_map.pop()
        # t = self.redo_transaction_map.pop()
        #
        # self.undo_id_map.append(id)
        # self.undo_transaction_map.append(t.copy())
        #
        # self.undo_redo_action(id, t.copy())
        #
        # self.transaction_map[id] = t.copy()
        # self.build_visible_transactions()
        return

    def build_names(self):
        self.transaction_names = {}
        self.category_names = {}
        for t in self.data['transactions']:
            self.transaction_names[t['name']] = 1
            self.category_names[t['category']] = 1

    def create_test_data(self):
        cur_date = datetime.date.today()
        cur_date = datetime.date(cur_date.year, cur_date.month, 1)
        self.create_transaction('Initial Balance', type='credit', amount=632,
                                category='Initial Balance', date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Fix Car', amount=75.84,
                                category='Transportation', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Adopt Cat', amount=100, category='Pets',
                                date=cur_date)
        self.create_transaction('New Coat', amount=25.53, category='Clothing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Pay Rent', amount=500, category='Housing',
                                date=cur_date)

        cur_date += datetime.timedelta(days=1)
        self.create_transaction('Funky Cafe', amount=5.20, category='Food',
                                date=cur_date)
        self.create_transaction('Groceries', amount=50.92, category='Food',
                                date=cur_date)
        self.create_transaction('Cat Food', amount=5.40, category='Pets',
                                date=cur_date)

        cur_date += datetime.timedelta(days=4)
        self.create_transaction('Paycheck', type='credit', amount=700,
                                category='Paycheck', date=cur_date)
        self.create_transaction('Gas', amount=21.20, category='Transportation',
                                date=cur_date)

        cur_date += datetime.timedelta(days=2)
        self.create_transaction('Cat Toys', amount=10.95, category='Pets',
                                date=cur_date)
        self.create_transaction('Gift for Sister', amount=23.20,
                                category='Gifts', date=cur_date)

        self.build_transaction_map()
        self.build_names()

    def read_file(self, file_path):
        if self.metadata['mime_type'] != 'text/plain':
            return

        fd = open(file_path, 'r')
        try:
            text = fd.read()
            self.data = json.loads(text)
        finally:
            fd.close()

        if self.data['transactions']:
            self._set_internal_panel(self.register)
        self.show_header_controls()

        self.build_transaction_map()
        self.build_names()
        self.build_screen()

    def write_file(self, file_path):
        if not self.metadata['mime_type']:
            self.metadata['mime_type'] = 'text/plain'

        fd = open(file_path, 'w')
        try:
            text = json.dumps(self.data)
            fd.write(text)
        finally:
            fd.close()

    def __save_image_cb(self, widget):
        image_file = tempfile.NamedTemporaryFile(mode='w+b', suffix='.png')
        journal_entry = datastore.create()
        journal_entry.metadata['title'] = self.chart.title
        journal_entry.metadata['keep'] = '0'
        journal_entry.metadata['mime_type'] = 'image/png'

        # generate the image
        self.chart.generate_image(image_file.file, 800, 600)
        image_file.file.close()
        journal_entry.file_path = image_file.name

        # generate the preview
        preview_str = io.BytesIO()
        self.chart.generate_image(preview_str, activity.PREVIEW_SIZE[0],
                                  activity.PREVIEW_SIZE[1])
        journal_entry.metadata['preview'] = dbus.ByteArray(
            preview_str.getvalue())

        logging.debug('Create %s image file', image_file.name)
        datastore.write(journal_entry)
        self._show_journal_alert(
            _('Chart created'), _('Open in the Journal'),
            journal_entry.object_id)

    def _show_journal_alert(self, title, msg, object_id):
        open_alert = Alert()
        open_alert.props.title = title
        open_alert.props.msg = msg
        open_icon = Icon(icon_name='zoom-activity')
        open_alert.add_button(Gtk.ResponseType.APPLY,
                              _('Show in Journal'), open_icon)
        open_icon.show()
        ok_icon = Icon(icon_name='dialog-ok')
        open_alert.add_button(Gtk.ResponseType.OK, _('Ok'), ok_icon)
        ok_icon.show()
        # Remove other alerts
        for alert in self._alerts:
            self.remove_alert(alert)

        self.add_alert(open_alert)
        open_alert.connect('response', self.__open_response_cb, object_id)
        open_alert.show()

    def __open_response_cb(self, alert, response_id, object_id):
        if response_id is Gtk.ResponseType.APPLY:
            activity.show_object_in_journal(object_id)
        self.remove_alert(alert)

    def __export_data_to_chart_cb(self, widget, type_movement, period):
        """
        type_movement = 'debit' or 'credit'
        period
            DAY = 0
            MONTH = 2
        """
        logging.debug('export data %s %s', type_movement, period)

        chart_params = {}
        axis = {'tickFont': 'Sans', 'labelFont': 'Sans', 'labelFontSize': 14,
                'labelColor': '#666666', 'lineColor': '#b3b3b3',
                'tickColor': '#000000', 'tickFontSize': 12}
        chart_params['font_options'] = {
            'titleFont': 'Sans', 'titleFontSize': 12, 'titleColor': '#000000',
            'axis': axis}

        if type_movement == 'credit':
            what_filter = 'Credits'
        elif type_movement == 'debit':
            what_filter = 'Debits'
        else:
            logging.debug('ERROR type_movement should be credit or debit')

        if period == DAY:
            when = 'day'
        elif period == MONTH:
            when = 'month'
        else:
            logging.debug('ERROR period should be DAY or MONTH')

        title = _('%(what_filter)s by %(when)s') % {
            'what_filter': what_filter, 'when': when}
        chart_params['title'] = title
        chart_params['x_label'] = ''
        chart_params['y_label'] = ''
        chart_params['current_chart.type'] = 1
        xo_color = profile.get_color()
        chart_params['chart_line_color'] = xo_color.get_stroke_color()
        chart_params['chart_color'] = xo_color.get_fill_color()

        """
        'chart_data': [
            ['hello', 200.0],
            ['mrch', 100.0]],
        """
        transactions = self.data['transactions']

        groups = {}
        for transaction in transactions:
            if transaction['type'] == type_movement:
                date = transaction['date']
                if period == DAY:
                    group = date
                elif period == MONTH:
                    d = datetime.date.fromordinal(date)
                    group = datetime.date(d.year, d.month, 1).toordinal()
                if group in list(groups.keys()):
                    groups[group] = groups[group] + transaction['amount']
                else:
                    groups[group] = transaction['amount']

        data = []
        for group in sorted(groups.keys()):
            if period == DAY:
                label = datetime.date.fromordinal(group).isoformat()
            elif period == MONTH:
                d = datetime.date.fromordinal(group)
                label = '%s-%s' % (d.year, d.month)

            data.append([label, groups[group]])

        chart_params['chart_data'] = data

        logging.debug('chart_data %s', chart_params)

        # save to the journal
        data_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json')
        journal_entry = datastore.create()
        journal_entry.metadata['title'] = title
        journal_entry.metadata['keep'] = '0'
        journal_entry.metadata['mime_type'] = 'application/x-chart-activity'
        journal_entry.metadata['activity'] = 'org.sugarlabs.SimpleGraph'

        json.dump(chart_params, data_file.file)
        data_file.file.close()
        journal_entry.file_path = data_file.name

        logging.debug('Create %s data file', data_file.name)
        datastore.write(journal_entry)
        self._show_journal_alert(
            _('Exported data'), _('Open in the Journal'),
            journal_entry.object_id)
