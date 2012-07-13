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
#!/usr/bin/env python

"""Finance - Home financial software for the OLPC XO."""

# Import standard Python modules.
import logging
import datetime
import locale

# Import screen classes.
import registerscreen
import chartscreen
import budgetscreen

from gettext import gettext as _
from port import json

from gi.repository import Gtk
from gi.repository import Gdk

# Import Sugar UI modules.
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolcombobox import ToolComboBox

from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.radiotoolbutton import RadioToolButton
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.activity import Activity

# Set up localization.
locale.setlocale(locale.LC_ALL, '')

# Initialize logging.
log = logging.getLogger('Finance')
log.setLevel(logging.DEBUG)
logging.basicConfig()


CATEGORY_COLORS = [
    (1.0, 1.0, 1.0),
    (1.0, 1.0, 0.6),
    (1.0, 1.0, 0.8),
    (1.0, 0.6, 1.0),
    (1.0, 0.6, 0.6),
    (1.0, 0.6, 0.8),
    (1.0, 0.8, 1.0),
    (1.0, 0.8, 0.6),
    (1.0, 0.8, 0.8),
    (0.6, 1.0, 1.0),
    (0.6, 1.0, 0.6),
    (0.6, 1.0, 0.8),
    (0.6, 0.6, 1.0),
    (0.6, 0.6, 0.6),
    (0.6, 0.6, 0.8),
    (0.6, 0.8, 1.0),
    (0.6, 0.8, 0.6),
    (0.6, 0.8, 0.8),
    (0.8, 1.0, 1.0),
    (0.8, 1.0, 0.6),
    (0.8, 1.0, 0.8),
    (0.8, 0.6, 1.0),
    (0.8, 0.6, 0.6),
    (0.8, 0.6, 0.8),
    (0.8, 0.8, 1.0),
    (0.8, 0.8, 0.6),
    (0.8, 0.8, 0.8),
]


def get_category_color(catname):
    return CATEGORY_COLORS[catname.__hash__() % len(CATEGORY_COLORS)]


def get_category_color_str(catname):
    color = get_category_color(catname)
    return "#%02x%02x%02x" % \
        (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))


# This is the main Finance activity class.
#
# It owns the main application window, and all the various toolbars
# and options. Screens are stored in a stack, with the currently
# active screen on top.
class Finance(Activity):
    def __init__(self, handle):
        Activity.__init__(self, handle)
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

        self.transaction_names = {}
        self.category_names = {}

        #self.create_test_data()

        # Initialize view period to the first of the month.
        self.period = _('Month')
        self.period_start = self.get_this_period()

        # Create screens.
        self.register = registerscreen.RegisterScreen(self)
        self.chart = chartscreen.ChartScreen(self)
        self.budget = budgetscreen.BudgetScreen(self)

        self.build_toolbox()

        self.screens = []
        self.screenbox = Gtk.VBox()

        # Add the context sensitive help.
        self.helplabel = Gtk.Label()
        self.helplabel.set_padding(10, 10)
        self.helpbox = Gtk.EventBox()
        parse, color = Gdk.Color.parse('#000000')
        self.helpbox.modify_bg(Gtk.StateType.NORMAL, color)
        self.helpbox.add(self.helplabel)

        # Add the header.
        self.periodlabel = Gtk.Label()
        self.periodlabel.set_padding(10, 0)

        headerbox = Gtk.HBox()
        headerbox.pack_end(self.periodlabel, False, False, 0)

        # Add the summary data.
        self.startlabel = Gtk.Label()
        self.creditslabel = Gtk.Label()
        self.debitslabel = Gtk.Label()
        self.balancelabel = Gtk.Label()

        summarybox = Gtk.HBox()
        summarybox.pack_start(self.startlabel, True, False, 0)
        summarybox.pack_start(self.creditslabel, True, False, 0)
        summarybox.pack_start(self.debitslabel, True, False, 0)
        summarybox.pack_start(self.balancelabel, True, False, 0)

        vbox = Gtk.VBox()

        vbox.pack_start(self.helpbox, False, False, 10)
        vbox.pack_start(headerbox, False, False, 10)
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
                        False, False, 0)
        vbox.pack_start(self.screenbox, True, True, 0)
        vbox.pack_start(summarybox, False, False, 10)

        # Start with the main screen.
        self.push_screen(self.register)

        # This has to happen last, because it calls the read_file
        # method when restoring from the Journal.
        self.set_canvas(vbox)

        self.show_all()

    def build_toolbox(self):
        self.newcreditbtn = ToolButton('row-insert-credit')
        self.newcreditbtn.set_tooltip(_("New Credit"))
        self.newcreditbtn.props.accelerator = '<Ctrl>A'
        self.newcreditbtn.connect('clicked', self.register.newcredit_cb)

        self.newdebitbtn = ToolButton('row-insert-debit')
        self.newdebitbtn.set_tooltip(_("New Debit"))
        self.newdebitbtn.props.accelerator = '<Ctrl>D'
        self.newdebitbtn.connect('clicked', self.register.newdebit_cb)

        self.eraseitembtn = ToolButton('row-remove-transaction')
        self.eraseitembtn.set_tooltip(_("Erase Transaction"))
        self.eraseitembtn.props.accelerator = '<Ctrl>E'
        self.eraseitembtn.connect('clicked', self.register.eraseitem_cb)

        transactionbar = Gtk.Toolbar()
        transactionbar.insert(self.newcreditbtn, -1)
        transactionbar.insert(self.newdebitbtn, -1)
        transactionbar.insert(self.eraseitembtn, -1)

        self.thisperiodbtn = ToolButton('go-down')
        self.thisperiodbtn.props.accelerator = '<Ctrl>Down'
        self.thisperiodbtn.connect('clicked', self.thisperiod_cb)

        self.prevperiodbtn = ToolButton('go-previous-paired')
        self.prevperiodbtn.props.accelerator = '<Ctrl>Left'
        self.prevperiodbtn.connect('clicked', self.prevperiod_cb)

        self.nextperiodbtn = ToolButton('go-next-paired')
        self.nextperiodbtn.props.accelerator = '<Ctrl>Right'
        self.nextperiodbtn.connect('clicked', self.nextperiod_cb)

        periodsep = Gtk.SeparatorToolItem()
        periodsep.set_expand(True)
        periodsep.set_draw(False)

        periodlabel = Gtk.Label(label=_('Period: '))
        periodlabelitem = Gtk.ToolItem()
        periodlabelitem.add(periodlabel)

        periodcombo = Gtk.ComboBoxText()
        periodcombo.append_text(_('Day'))
        periodcombo.append_text(_('Week'))
        periodcombo.append_text(_('Month'))
        periodcombo.append_text(_('Year'))
        periodcombo.append_text(_('Forever'))
        periodcombo.set_active(2)
        periodcombo.connect('changed', self.period_changed_cb)

        perioditem = ToolComboBox(periodcombo)

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

        viewbar = Gtk.Toolbar()
        viewbar.insert(registerbtn, -1)
        viewbar.insert(budgetbtn, -1)
        viewbar.insert(chartbtn, -1)

        helpbtn = ToggleToolButton('help')
        helpbtn.set_active(True)
        helpbtn.set_tooltip(_("Show Help"))
        helpbtn.connect('clicked', self.help_cb)

        self.toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.show()

        transaction_toolbar_button = ToolbarButton(
            page=transactionbar,
            icon_name='transaction')
        transactionbar.show_all()

        view_toolbar_button = ToolbarButton(
            page=viewbar,
            icon_name='toolbar-view')
        viewbar.show_all()

        self.toolbar_box.toolbar.insert(transaction_toolbar_button, -1)
        transaction_toolbar_button.show()

        self.toolbar_box.toolbar.view = view_toolbar_button
        self.toolbar_box.toolbar.insert(view_toolbar_button, -1)
        view_toolbar_button.show()

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        self.toolbar_box.toolbar.insert(separator, -1)

        self.toolbar_box.toolbar.insert(periodlabelitem, -1)
        self.toolbar_box.toolbar.insert(perioditem, -1)
        self.toolbar_box.toolbar.insert(self.prevperiodbtn, -1)
        self.toolbar_box.toolbar.insert(self.nextperiodbtn, -1)
        self.toolbar_box.toolbar.insert(self.thisperiodbtn, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)

        self.toolbar_box.toolbar.insert(helpbtn, -1)
        self.toolbar_box.toolbar.insert(StopButton(self), -1)
        self.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show_all()

    def set_help(self, text):
        if self.helplabel != None:
            self.helplabel.set_markup('<span size="8000" color="#ffffff">' +
                    text + '</span>')

    def help_cb(self, widget):
        if widget.get_active():
            self.helpbox.show()
        else:
            self.helpbox.hide()

    def register_cb(self, widget):
        self.pop_screen()
        self.push_screen(self.register)

    def budget_cb(self, widget):
        self.pop_screen()
        self.push_screen(self.budget)

    def chart_cb(self, widget):
        self.pop_screen()
        self.push_screen(self.chart)

    def push_screen(self, screen):
        if len(self.screens):
            self.screenbox.remove(self.screens[-1])

        self.screenbox.pack_start(screen, True, True, 0)
        self.screens.append(screen)

        self.build_screen()

    def pop_screen(self):
        self.screenbox.remove(self.screens[-1])
        self.screens.pop()
        if len(self.screens):
            self.screenbox.pack_start(self.screens[-1], True, True, 0)

    def build_screen(self):
        self.build_visible_transactions()

        if len(self.screens):
            self.screens[-1].build()

        self.update_header()
        self.update_summary()
        self.update_toolbar()

    def update_header(self):
        if self.period == _('Day'):
            # TRANS: representation of the "Day" period
            text = self.period_start.strftime(_("%B %d, %Y"))

        elif self.period == _('Week'):
            # TRANS: representation of the "Week of" period
            text = _('Week of') + self.period_start.strftime(_(" %B %d, %Y"))

        elif self.period == _('Month'):
            # TRANS: representation of the "Month" period
            text = self.period_start.strftime(_("%B, %Y"))

        elif self.period == _('Year'):
            # TRANS: representation of the "Year" period
            text = self.period_start.strftime(_("%Y"))

        elif self.period == _('Forever'):
            text = _('Forever')

        self.periodlabel.set_markup(
            "<span size='xx-large'><b>" + text + "</b></span>")

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
            balancecolor = '#4040ff'
        else:
            balancecolor = '#ff4040'
        balance = "<span size='xx-large' foreground='%s'><b>" % balancecolor
        balance += _('Balance: ') + locale.currency(total)
        balance += "</b></span>"
        self.balancelabel.set_markup(balance)

        self.startlabel.set_markup('Starting Balance: ' +
                                   locale.currency(start))
        self.creditslabel.set_markup(
            '%s in %d credits' % (locale.currency(credit_total), credit_count))
        self.debitslabel.set_markup(
            '%s in %d debits' % (locale.currency(debit_total), debit_count))

    def update_toolbar(self):
        # Disable the navigation when Forever is selected.
        next_prev = self.period != _('Forever')
        self.prevperiodbtn.set_sensitive(next_prev)
        self.thisperiodbtn.set_sensitive(next_prev)
        self.nextperiodbtn.set_sensitive(next_prev)

        # This is a HACK to translate the string properly
        # http://bugs.sugarlabs.org/ticket/3190
        period = self.period.lower()
        if period == _('Month').lower():
            text_previous_period = _('Previous Month')
            text_this_period = _('This Month')
            text_next_period = _('Next Month')
        elif period == _('Day').lower():
            text_previous_period = _('Previous Day')
            text_this_period = _('This Day')
            text_next_period = _('Next Day')
        elif period == _('Year').lower():
            text_previous_period = _('Previous Year')
            text_this_period = _('This Year')
            text_next_period = _('Next Year')

        # Update the label self.period to reflect the period.
        self.prevperiodbtn.set_tooltip(text_previous_period)
        self.thisperiodbtn.set_tooltip(text_this_period)
        self.nextperiodbtn.set_tooltip(text_next_period)

        # Only add and delete transactions on register screen.
        add_del = self.screens[-1] == self.register
        self.newcreditbtn.set_sensitive(add_del)
        self.newdebitbtn.set_sensitive(add_del)
        self.eraseitembtn.set_sensitive(add_del)

    def get_this_period(self):
        today = datetime.date.today()

        if self.period == _('Day'):
            return today

        elif self.period == _('Week'):
            while today.weekday() != 0:
                today -= datetime.timedelta(days=1)
            return today

        elif self.period == _('Month'):
            return datetime.date(today.year, today.month, 1)

        elif self.period == _('Year'):
            return datetime.date(today.year, 1, 1)

        elif self.period == _('Forever'):
            return datetime.date(1900, 1, 1)

    def get_next_period(self, start):
        if self.period == _('Day'):
            return start + datetime.timedelta(days=1)

        elif self.period == _('Week'):
            return start + datetime.timedelta(days=7)

        elif self.period == _('Month'):
            if start.month == 12:
                return datetime.date(start.year + 1, 1, 1)
            else:
                return datetime.date(start.year, start.month + 1, 1)

        elif self.period == _('Year'):
            return datetime.date(start.year + 1, 1, 1)

    def get_prev_period(self, start):
        if self.period == _('Day'):
            return start - datetime.timedelta(days=1)

        elif self.period == _('Week'):
            return start - datetime.timedelta(days=7)

        elif self.period == _('Month'):
            if start.month == 1:
                return datetime.date(start.year - 1, 12, 1)
            else:
                return datetime.date(start.year, start.month - 1, 1)

        elif self.period == _('Year'):
            return datetime.date(start.year - 1, 1, 1)

    def thisperiod_cb(self, widget):
        if self.period != _('Forever'):
            self.period_start = self.get_this_period()
            self.build_screen()

    def nextperiod_cb(self, widget):
        if self.period != _('Forever'):
            self.period_start = self.get_next_period(self.period_start)
            self.build_screen()

    def prevperiod_cb(self, widget):
        if self.period != _('Forever'):
            self.period_start = self.get_prev_period(self.period_start)
            self.build_screen()

    def period_changed_cb(self, widget):
        self.period = widget.get_active_text()
        self.update_toolbar()

        # Jump to 'this period'.
        self.period_start = self.get_this_period()
        self.build_screen()

    def build_visible_transactions(self):
        if self.period == _('Forever'):
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

        self.visible_transactions.sort(lambda a, b: a['date'] - b['date'])

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
