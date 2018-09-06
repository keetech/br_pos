# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models, fields, _
from odoo.addons.point_of_sale.wizard.pos_box import PosBoxIn, PosBoxOut

class PosSession(models.Model):
    _inherit = 'pos.session'

    qty_orders = fields.Integer(string=u'Quant. de Vendas', compute='_compute_orders')
    amount_total_orders = fields.Monetary(string=u'Valor Total Vendas', compute='_compute_orders')
    cash_move_ids = fields.One2many('pos.session.cash.move', 'pos_session_id', string=u'Depósitos/Retiradas')
    total_cash_move_out = fields.Monetary(string=u'Total de Retiradas', compute='_compute_cash_move')
    total_cash_move_in = fields.Monetary(string=u'Total de Depósitos', compute='_compute_cash_move')
    total_cash_move_closing = fields.Monetary(string=u'Total de Depósitos', compute='_compute_cash_move')
    total_cash_move_balance = fields.Monetary(string=u'Balanço dos Depósitoes/Sangrias', compute='_compute_cash_move')
    total_cash_move_sales = fields.Monetary(string=u'Vendas em Espécie', compute='_compute_cash_move')

    @api.one
    @api.depends('order_ids')
    def _compute_orders(self):
        for session in self:
            amount_total_orders = 0
            qty_orders = len(session.order_ids)
            session.qty_orders = qty_orders
            for order in session.order_ids:
                amount_total_orders += order.amount_paid
            session.amount_total_orders = amount_total_orders

    @api.one
    @api.depends('cash_move_ids')
    def _compute_cash_move(self):
        total_out = 0
        total_in = 0
        total_closing = 0
        for line in self.cash_move_ids:
            if line.type == 'in':
                total_in += line.amount
            if line.type == 'out':
                total_out += line.amount
            if line.type == 'closing':
                total_closing += line.amount
        balance = total_in - ((total_out + total_closing) * -1)
        self.total_cash_move_sales = self.cash_register_total_entry_encoding - balance
        self.total_cash_move_out = total_out
        self.total_cash_move_in = total_in
        self.total_cash_move_closing = total_closing
        self.total_cash_move_balance = self.total_cash_move_sales + balance

class PosSessionCashMove(models.Model):
    _name = 'pos.session.cash.move'

    pos_session_id = fields.Many2one('pos.session', string="Session", copy=False)
    user_id = fields.Many2one('res.users', string='Responsible', required=True, index=True, readonly=True,
                              default=lambda self: self.env.uid)
    currency_id = fields.Many2one('res.currency', string="Moeda")
    reference = fields.Char(string='Referência', copy=False, readonly=True)
    amount = fields.Monetary(digits=2, string=u'Valor do Depóstio/Sangria')
    type = fields.Selection([('out', u'Saque/Sangria'), ('in', u'Depósito'), ('closing', u'Fechamento')],
                            string=u'Tipo de Movimentação')

    @api.multi
    def action_print_move(self):
            return self.env.ref(
                'br_point_sale.br_pos_session_move_cash').report_action(self)

class PosBoxIn(PosBoxIn):

    _inherit = 'cash.box.in'

    @api.multi
    def register_cash_move(self, session_id):
        cash_move = self.env['pos.session.cash.move']
        values = {
            'amount': self.amount,
            'user_id': self.env.uid,
            'type': 'in',
            'reference': self.name,
            'pos_session_id': session_id,
        }

        move = cash_move.create(values)

        try:
            report_move = self.env['ir.actions.report'].search(
                [('report_name', '=', 'br_point_sale.br_pos_session_move_report')])

            report_move[0].print_document(record_ids=[move.id])

        except Exception:
            pass

    def _calculate_values_for_statement_line(self, record):
        values = super(PosBoxIn, self)._calculate_values_for_statement_line(record=record)
        active_model = self.env.context.get('active_model', False)
        active_ids = self.env.context.get('active_ids', [])
        if active_model == 'pos.session' and active_ids:
            values['ref'] = self.env[active_model].browse(active_ids)[0].name
            session_id = self.env[active_model].browse(active_ids)[0].id
            self.register_cash_move(session_id)
        return values

class PosBoxOut(PosBoxOut):

    _inherit = 'cash.box.out'

    @api.multi
    def register_cash_move(self, session_id, type='out'):
        cash_move = self.env['pos.session.cash.move']
        values = {
            'amount': self.amount * -1,
            'user_id': self.env.uid,
            'reference': self.name,
            'type': type,
            'pos_session_id': session_id,
        }

        move = cash_move.create(values)

        if type == 'out':
            try:
                report_move = self.env['ir.actions.report'].search(
                    [('report_name', '=', 'br_point_sale.br_pos_session_move_report')])

                report_move[0].print_document(record_ids=[move.id])
            except Exception:
                pass

    def _calculate_values_for_statement_line(self, record):
        values = super(PosBoxOut, self)._calculate_values_for_statement_line(record=record)
        active_model = self.env.context.get('active_model', False)
        active_ids = self.env.context.get('active_ids', [])
        if active_model == 'pos.session' and active_ids:
            values['ref'] = self.env[active_model].browse(active_ids)[0].name
            session_id = self.env[active_model].browse(active_ids)[0].id
            if self.env[active_model].browse(active_ids)[0].state == 'closing_control':
                type = 'closing'
            else:
                type = 'out'
            self.register_cash_move(session_id, type=type)
        return values