# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime
from random import SystemRandom
from odoo.addons import decimal_precision as dp
from odoo import api, models, fields, _

from odoo.addons.br_account.models.cst import CST_ICMS
from odoo.addons.br_account.models.cst import CSOSN_SIMPLES
from odoo.addons.br_account.models.res_company import COMPANY_FISCAL_TYPE

# TODO: Revisar cadastros nas posições fiscais
# TODO: quando for NFC-e não permitir operação não-presencial
# TODO: verificar a diferença entre os campos 'numero' e 'numero_nfe'

class PosOrder(models.Model):
    _inherit = 'pos.order'

    numero_controle = fields.Integer()
    cnpj_cpf = fields.Char(string=u'CNPJ/CPF')
    sequence_number = fields.Integer(string='Sequence Number', help='A session-unique sequence number for the order',
                                     default=1)
#    total_bruto = fields.Float() TODO
#    total_without_tax = fields.Float() TODO
#    total_tax = fields.Float() TODO
#    total_desconto = fields.Float() TODO

    def action_number(self, serie_id):
        # Busca número sequencial da NF-e
        if not serie_id:
            return

        inv_inutilized = self.env['invoice.eletronic.inutilized'].search([
            ('serie', '=', serie_id.id)], order='numeration_end desc', limit=1)

        if not inv_inutilized:
            return serie_id.internal_sequence_id.next_by_id()

        if inv_inutilized.numeration_end >= \
                serie_id.internal_sequence_id.number_next_actual:
            serie_id.internal_sequence_id.write(
                {'number_next_actual': inv_inutilized.numeration_end + 1})
            return serie_id.internal_sequence_id.next_by_id()

    @api.depends('statement_ids', 'lines.price_subtotal_incl', 'lines.discount')
    def _compute_amount_all(self):
        super(PosOrder, self)._compute_amount_all()
        for order in self:
            for product in order.lines:
                order.total_icms += product.valor_icms
                order.total_pis += product.valor_pis
                order.total_cofins += product.valor_cofins


    @api.model
    def _process_order(self, pos_order):
        num_controle = int(''.join([str(SystemRandom().randrange(9)) for i in range(8)]))
        res = super(PosOrder, self)._process_order(pos_order)
        res.numero_controle = str(num_controle)
        if not res.fiscal_position_id:
            res.fiscal_position_id = res.session_id.config_id.default_fiscal_position_id.id
        # todo: refatorar
        for line in res.lines:
            ncm = line.product_id.fiscal_classification_id
            fiscal_classification_id = ncm.id
            line.update({'fiscal_classification_id' : fiscal_classification_id})

        for line in res.lines:
            values = line.order_id.fiscal_position_id.map_tax_extra_values(line.company_id, line.product_id,
                                                                           line.order_id.partner_id)
            
            empty = self.env['account.tax'].browse()
            tax_ids = values.get('tax_icms_id', empty) | \
                values.get('tax_icms_st_id', empty) | \
                values.get('tax_icms_inter_id', empty) | \
                values.get('tax_icms_intra_id', empty) | \
                values.get('tax_icms_fcp_id', empty) | \
                values.get('tax_ipi_id', empty) | \
                values.get('tax_pis_id', empty) | \
                values.get('tax_cofins_id', empty) | \
                values.get('tax_ii_id', empty) | \
                values.get('tax_issqn_id', empty)

            other_taxes = line.tax_ids.filtered(lambda x: not x.domain)
            tax_ids |= other_taxes
            
            line.update({
                'tax_ids': [(6, None, [x.id for x in tax_ids if x])]
            })

            for key, value in values.items():
                if value and key in line._fields:
                    line.update({key: value})
        
        foo = self._prepare_edoc_vals(res)
        edoc = self.env['invoice.eletronic']
        #docs = self.env['invoice.eletronic'].search([('pos_order_reference', '=', pos_reference)])
        ''''''
        pos_order_eletronic = edoc.create(foo)
        pos_order_eletronic.validate_invoice()
        pos_order_eletronic.action_post_validate()
        try:
            if len(edoc.search([('pos_order_reference', '=', res.pos_reference)])) == 0:
                pos_order_eletronic.action_send_eletronic_invoice()
            else:
                pos_order_eletronic = edoc.search([('pos_order_reference', '=', res.pos_reference)])
        except Exception:
            pass
        #reports = self.env['ir.actions.report'].print_action_for_report_name('br_nfe.main_template_br_nfe_danfe')
        try:
            report_danfce = self.env['ir.actions.report'].search(
                [('report_name', '=', 'br_point_sale.main_template_br_nfe_danfce')])

            report_danfce[0].print_document(record_ids=pos_order_eletronic.ids)
        except Exception:
            pass
            

        return res


    def _action_create_invoice_line(self, line=False, invoice_id=False):
        InvoiceLine = self.env['account.invoice.line']
        inv_name = line.product_id.name_get()[0][1]
        ncm = line.product_id.fiscal_classification_id
        res.lines.fiscal_classification_id = ncm.id
        inv_line = {
            'invoice_id': invoice_id,
            'product_id': line.product_id.id,
            'quantity': line.qty,
            'account_analytic_id': self._prepare_analytic_account(line),
            'name': inv_name, 
        }
        # Oldlin trick
        invoice_line = InvoiceLine.sudo().new(inv_line)
        invoice_line._onchange_product_id()
        ncm = line.product_id.fiscal_classification_id
        invoice_line.fiscal_classification_id = ncm.id
        invoice_line.invoice_line_tax_ids = invoice_line.invoice_line_tax_ids.filtered(lambda t: t.company_id.id == line.order_id.company_id.id).ids
        fiscal_position_id = line.order_id.fiscal_position_id
        if fiscal_position_id:
            invoice_line.invoice_line_tax_ids = fiscal_position_id.map_tax(invoice_line.invoice_line_tax_ids, line.product_id, line.order_id.partner_id)
        invoice_line.invoice_line_tax_ids = invoice_line.invoice_line_tax_ids.ids
        # We convert a new id object back to a dictionary to write to
        # bridge between old and new api
        inv_line = invoice_line._convert_to_write({name: invoice_line[name] for name in invoice_line._cache})
        inv_line.update(price_unit=line.price_unit, discount=line.discount)
        return InvoiceLine.sudo().create(inv_line)
        
    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a pos order.
        """
        return {
            'name': self.name,
            'origin': self.name,
            'account_id': self.partner_id.property_account_receivable_id.id,
            'journal_id': self.session_id.config_id.invoice_journal_id.id,
            'type': 'out_invoice',
            'reference': self.name,
            'partner_id': self.partner_id.id,
            'comment': self.note or '',
            # considering partner's sale pricelist's currency
            'currency_id': self.pricelist_id.currency_id.id,
            'user_id': self.env.uid,
            'metodo_pagamento': self.statement_ids[0].journal_id.metodo_pagamento
        }

    def _prepare_edoc_item_vals(self, pos_line):
        vals = {
            'name': pos_line.name,
            'product_id': pos_line.product_id.id,
            'tipo_produto': pos_line.product_id.fiscal_type,
            'cfop': pos_line.cfop_id.code,
            'cest': pos_line.product_id.cest or
                pos_line.product_id.fiscal_classification_id.cest or '',
            'uom_id': pos_line.product_id.uom_id.id,
            'ncm': pos_line.product_id.fiscal_classification_id.code,
            'quantidade': pos_line.qty,
            'preco_unitario': pos_line.price_unit,
            'valor_bruto': pos_line.price_subtotal_incl,
            'valor_liquido': pos_line.price_subtotal,
            'origem': pos_line.product_id.origin,
            'tributos_estimados': (
                pos_line.price_subtotal_incl - pos_line.price_subtotal
            ),
            # - ICMS -
            'icms_cst': pos_line.icms_cst,
            'icms_aliquota': pos_line.aliquota_icms,
            'icms_tipo_base': '3',
            'icms_aliquota_reducao_base': pos_line.icms_aliquota_reducao_base,
            'icms_base_calculo': pos_line.base_icms,
            'icms_valor': pos_line.valor_icms,
            # - ICMS ST -
            'icms_st_aliquota': 0,
            'icms_st_aliquota_mva': 0,
            'icms_st_aliquota_reducao_base': pos_line.icms_st_aliquota_reducao_base,
            'icms_st_base_calculo': 0,
            'icms_st_valor': 0,
            # - Simples Nacional -
            'icms_aliquota_credito': 0,
            'icms_valor_credito': 0,
            # - II -
            'ii_base_calculo': 0,
            'ii_valor_despesas': 0,
            'ii_valor': 0,
            'ii_valor_iof': 0,
            # - PIS -
            'pis_cst': pos_line.pis_cst,
            'pis_aliquota': pos_line.aliquota_pis,
            'pis_base_calculo': pos_line.base_pis,
            'pis_valor': pos_line.valor_pis,
            # - COFINS -
            'cofins_cst': pos_line.cofins_cst,
            'cofins_aliquota': pos_line.aliquota_cofins,
            'cofins_base_calculo': pos_line.base_cofins,
            'cofins_valor': pos_line.valor_cofins,
            # - ISSQN -
            'issqn_codigo': 0,
            'issqn_aliquota': 0,
            'issqn_base_calculo': 0,
            'issqn_valor': 0,
            'issqn_valor_retencao': 0.00,

        }
        return vals

    @api.multi
    def _prepare_edoc_vals(self, pos):
        numero_nfe = self.action_number(pos.fiscal_position_id.product_serie_id)
        vals = {
            'code': pos.sequence_number,
            'name': u'Documento Eletrônico: nº %s' % numero_nfe,
            'pos_order_reference': pos.pos_reference,
            'company_id': pos.company_id.id,
            'state': 'draft',
            'tipo_operacao': 'saida',
            'model': '65',
            'serie': pos.fiscal_position_id.product_serie_id.id,
            'numero': numero_nfe,
            'numero_controle': pos.numero_controle,
            'numero_nfe': numero_nfe,
            'data_emissao': datetime.now(),
            'data_fatura': datetime.now(),
            'finalidade_emissao': '1',
            'partner_id': pos.partner_id.id,
            'payment_term_id': None,
            'fiscal_position_id': pos.fiscal_position_id.id,
            'ind_final': pos.fiscal_position_id.ind_final,
            'ind_pres': pos.fiscal_position_id.ind_pres,
            #'metodo_pagamento': pos.statement_ids[0].journal_id.payment_mode.payment_method,
            'ambiente': 'homologacao' if pos.company_id.tipo_ambiente == '2' else 'producao',
        }


        valor_pago = 0
        troco = 0
        payments = []
        for payment in pos.statement_ids:
            if payment.amount > 0:
                payments.append((0, 0,
                                {'metodo_pagamento': payment.journal_id.payment_mode.payment_method,
                                 'valor': payment.amount}))
                valor_pago += payment.amount
            if payment.amount < 0:
                troco += payment.amount
        base_icms = 0
        base_cofins = 0
        base_pis = 0
        eletronic_items = []
        for pos_line in pos.lines:
            eletronic_items.append((0, 0, self._prepare_edoc_item_vals(pos_line)))
            base_icms += pos_line.base_icms
            base_pis += pos_line.base_pis
            base_cofins += pos_line.base_cofins

        vals['payment_ids'] = payments
        vals['eletronic_item_ids'] = eletronic_items
        vals['valor_bc_icms'] = pos.amount_paid - pos.amount_tax
        vals['fatura_liquido'] = pos.amount_paid - pos.amount_tax
        vals['valor_icms'] = pos.total_icms
        vals['valor_pis'] = pos.total_pis
        vals['valor_cofins'] = pos.total_cofins
        vals['valor_ii'] = 0
        vals['valor_bruto'] = pos.amount_paid - pos.amount_tax
        vals['valor_desconto'] = pos.amount_tax
        vals['valor_final'] = pos.amount_total
        # todo: refatorar para buscar valor apenas quando for pago
        vals['fatura_liquido'] = valor_pago
        vals['troco'] = (troco * -1) if troco != 0 else 0
        vals['valor_final'] = pos.amount_paid - pos.amount_tax
        #vals['valor_bc_icms'] = base_icms
        vals['valor_bc_icmsst'] = 0

        return vals


    @api.multi
    def _compute_total_edocs(self):
        for item in self:
            item.total_edocs = self.env['invoice.eletronic'].search_count(
                [('numero_controle', '=', self.numero_controle)])

    total_edocs = fields.Integer(string="Total NFe", compute=_compute_total_edocs)

    @api.multi
    def action_view_edocs(self):
        if self.total_edocs == 1:
            edoc = self.env['invoice.eletronic'].search(
                [('numero_controle', '=', self.numero_controle)], limit=1)
            dummy, act_id = self.env['ir.model.data'].get_object_reference(
                'br_account_einvoice', 'action_sped_base_eletronic_doc')
            dummy, view_id = self.env['ir.model.data'].get_object_reference(
                'br_account_einvoice', 'br_account_invoice_eletronic_form')
            vals = self.env['ir.actions.act_window'].browse(act_id).read()[0]
            vals['view_id'] = (view_id, u'sped.eletronic.doc.form')
            vals['views'][1] = (view_id, u'form')
            vals['views'] = [vals['views'][1], vals['views'][0]]
            vals['res_id'] = edoc.id
            vals['search_view'] = False
            return vals
        else:
            dummy, act_id = self.env['ir.model.data'].get_object_reference(
                'br_account_einvoice', 'action_sped_base_eletronic_doc')
            vals = self.env['ir.actions.act_window'].browse(act_id).read()[0]
            return vals

    @api.model
    def _amount_line_tax(self, line, fiscal_position_id):
        taxes = line.tax_ids.filtered(
            lambda t: t.company_id.id == line.order_id.company_id.id)
        if fiscal_position_id:
            taxes = fiscal_position_id.map_tax(
                taxes, line.product_id, line.order_id.partner_id)
        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        taxes = taxes.compute_all(
            price, line.order_id.pricelist_id.currency_id, line.qty,
            product=line.product_id,
            partner=line.order_id.partner_id or False)
        return taxes['total_included'] - taxes['total_excluded']

    total_icms = fields.Float(string='ICMS', compute=_compute_amount_all)
    total_pis = fields.Float(string='PIS', compute=_compute_amount_all)
    total_cofins = fields.Float(string='COFINS', compute=_compute_amount_all)

    @api.model
    def _get_account_move_line_group_data_type_key(self, data_type, values):
        """
        Return a tuple which will be used as a key for grouping account
        move lines in _create_account_move_line method.
        :param data_type: 'product', 'tax', ....
        :param values: account move line values
        :return: tuple() representing the data_type key
        """
        if data_type == 'product':
            return ('product',
                    values['partner_id'],
                    (values['product_id'], tuple(values['tax_ids'][0][2]), values['name']),
                    values['analytic_account_id'],
                    values['debit'] > 0)
        elif data_type == 'tax':
            return ('tax',
                    values['partner_id'],
                    values['tax_line_id'],
                    values['debit'] > 0)
        elif data_type == 'counter_part':
            return ('counter_part',
                    values['partner_id'],
                    values['account_id'],
                    values['debit'] > 0)
        return False

    def _create_account_move_line(self, session=None, move=None):
        # Função refatorada para br_point_of_sale
        # Não foi usada herança
        def _flatten_tax_and_children(taxes, group_done=None):
            children = self.env['account.tax']
            if group_done is None:
                group_done = set()
            for tax in taxes.filtered(lambda t: t.amount_type == 'group'):
                if tax.id not in group_done:
                    group_done.add(tax.id)
                    children |= _flatten_tax_and_children(tax.children_tax_ids, group_done)
            return taxes + children

        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        IrProperty = self.env['ir.property']
        ResPartner = self.env['res.partner']

        if session and not all(session.id == order.session_id.id for order in self):
            raise UserError(_('Ordens selecionadas não são da mesma Sessão'))

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False
        rounding_method = session and session.config_id.company_id.tax_calculation_rounding_method

        def add_anglosaxon_lines(grouped_data):
            Product = self.env['product.product']
            Analytic = self.env['account.analytic.account']
            for product_key in list(grouped_data.keys()):
                if product_key[0] == "product":
                    line = grouped_data[product_key][0]
                    product = Product.browse(line['product_id'])
                    # In the SO part, the entries will be inverted by function compute_invoice_totals
                    price_unit = self._get_pos_anglo_saxon_price_unit(product, line['partner_id'], line['quantity'])
                    account_analytic = Analytic.browse(line.get('analytic_account_id'))
                    res = Product._anglo_saxon_sale_move_lines(
                        line['name'], product, product.uom_id, line['quantity'], price_unit,
                        fiscal_position=order.fiscal_position_id,
                        account_analytic=account_analytic)
                    if res:
                        line1, line2 = res
                        line1 = Product._convert_prepared_anglosaxon_line(line1, order.partner_id)
                        insert_data('counter_part', {
                            'name': line1['name'],
                            'account_id': line1['account_id'],
                            'credit': line1['credit'] or 0.0,
                            'debit': line1['debit'] or 0.0,
                            'partner_id': line1['partner_id']

                        })

                        line2 = Product._convert_prepared_anglosaxon_line(line2, order.partner_id)
                        insert_data('counter_part', {
                            'name': line2['name'],
                            'account_id': line2['account_id'],
                            'credit': line2['credit'] or 0.0,
                            'debit': line2['debit'] or 0.0,
                            'partner_id': line2['partner_id']
                        })

        for order in self.filtered(lambda o: not o.account_move or o.state == 'paid'):
            current_company = order.sale_journal.company_id
            account_def = IrProperty.get(
                'property_account_receivable_id', 'res.partner')
            order_account = order.partner_id.property_account_receivable_id.id or account_def and account_def.id
            partner_id = ResPartner._find_accounting_partner(order.partner_id).id or False
            if move is None:
                # Cria uma entrada para a Venda
                journal_id = self.env['ir.config_parameter'].sudo().get_param(
                    'pos.closing.journal_id_%s' % current_company.id, default=order.sale_journal.id)
                move = self._create_account_move(
                    order.session_id.start_at, order.name, int(journal_id), order.company_id.id)

            def insert_data(data_type, values):
                # if have_to_group_by:
                values.update({
                    'partner_id': partner_id,
                    'move_id': move.id,
                })

                key = self._get_account_move_line_group_data_type_key(data_type, values)
                if not key:
                    return

                grouped_data.setdefault(key, [])

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        current_value = grouped_data[key][0]
                        current_value['quantity'] = current_value.get('quantity', 0.0) + values.get('quantity', 0.0)
                        current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                        current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                else:
                    grouped_data[key].append(values)

            # because of the weird way the pos order is written, we need to make sure there is at least one line,
            # because just after the 'for' loop there are references to 'line' and 'income_account' variables (that
            # are set inside the for loop)
            # TOFIX: a deep refactoring of this method (and class!) is needed
            # in order to get rid of this stupid hack
            assert order.lines, _('Não há nenhuma linha na ordem de venda!')
            # Cria um move para cada linha do pedido
            cur = order.pricelist_id.currency_id
            for line in order.lines:
                amount = line.price_subtotal

                # Search for the income account
                if line.product_id.property_account_income_id.id:
                    income_account = line.product_id.property_account_income_id.id
                elif line.product_id.categ_id.property_account_income_categ_id.id:
                    income_account = line.product_id.categ_id.property_account_income_categ_id.id
                else:
                    raise UserError(_('Please define income '
                                      'account for this product: "%s" (id:%d).')
                                    % (line.product_id.name, line.product_id.id))

                name = line.product_id.name
                if line.notice:
                    # Adicionar motivo do desconto ao 'move'
                    name = name + ' (' + line.notice + ')'

                # Create a move for the line for the order line
                # Just like for invoices, a group of taxes must be present on this base line
                # As well as its children
                base_line_tax_ids = _flatten_tax_and_children(line.tax_ids_after_fiscal_position).filtered(
                    lambda tax: tax.type_tax_use in ['sale', 'none'])
                insert_data('product', {
                    'name': name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'analytic_account_id': self._prepare_analytic_account(line),
                    'credit': ((amount > 0) and amount) or 0.0,
                    'debit': ((amount < 0) and -amount) or 0.0,
                    'tax_ids': [(6, 0, base_line_tax_ids.ids)],
                    'partner_id': partner_id
                })

                # Create the tax lines
                taxes = line.tax_ids_after_fiscal_position.filtered(lambda t: t.company_id.id == current_company.id)
                if not taxes:
                    continue
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                for tax in taxes.compute_all(price, cur, line.qty)['taxes']:
                    insert_data('tax', {
                        'name': _('Tax') + ' ' + tax['name'],
                        'product_id': line.product_id.id,
                        'quantity': line.qty,
                        'account_id': tax['account_id'] or income_account,
                        'credit': ((tax['amount'] > 0) and tax['amount']) or 0.0,
                        'debit': ((tax['amount'] < 0) and -tax['amount']) or 0.0,
                        'tax_line_id': tax['id'],
                        'partner_id': partner_id
                    })

            # round tax lines per order
            if rounding_method == 'round_globally':
                for group_key, group_value in grouped_data.items():
                    if group_key[0] == 'tax':
                        for line in group_value:
                            line['credit'] = cur.round(line['credit'])
                            line['debit'] = cur.round(line['debit'])

            # counterpart
            insert_data('counter_part', {
                'name': _("Trade Receivables"),  # order.name,
                'account_id': order_account,
                'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
                'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
                'partner_id': partner_id
            })

            order.write({'state': 'done', 'account_move': move.id})

        if self and order.company_id.anglo_saxon_accounting:
            add_anglosaxon_lines(grouped_data)

        all_lines = []
        for group_key, group_data in grouped_data.items():
            for value in group_data:
                all_lines.append((0, 0, value), )

        if move:  # In case no order was changed
            move.sudo().write({'line_ids': all_lines})
            move.sudo().post()
        return True


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def _default_company_fiscal_type(self):
        if self.order_id:
            return self.order_id.company_id.fiscal_type
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        return company.fiscal_type
        
    def _prepare_tax_context(self):
        return {
            'icms_st_aliquota_mva': self.icms_st_aliquota_mva,
            'icms_aliquota_reducao_base': self.icms_aliquota_reducao_base,
            'icms_st_aliquota_reducao_base':
            self.icms_st_aliquota_reducao_base,
            'icms_base_calculo': self.base_icms,
            'pis_base_calculo': self.base_pis,
            'cofins_base_calculo': self.base_cofins,
        }

    @api.depends('price_unit', 'tax_ids', 'qty', 'discount', 'product_id')
    def _compute_amount_line_all(self):
        #super(PosOrderLine, self)._compute_amount_line_all()
        for line in self:
            currency = line.order_id.pricelist_id.currency_id
            values = line.order_id.fiscal_position_id.map_tax_extra_values(
                line.company_id, line.product_id, line.order_id.partner_id)
            tax_ids = [values.get('tax_icms_id', False),
                       values.get('tax_icms_st_id', False),
                       values.get('tax_ipi_id', False),
                       values.get('tax_pis_id', False),
                       values.get('tax_cofins_id', False),
                       values.get('tax_ii_id', False),
                       values.get('tax_issqn_id', False)]

            line.update({'tax_ids': [(4, None, [x.id for x in tax_ids if x])]})
            line.cfop_id = values['cfop_id'].code if values.get('cfop_id', False) else False
            line.icms_cst = values.get('icms_cst_normal', False) if values.get('icms_cst_normal',
                                                                    False) else values.get('icms_csosn_simples', False)
            line.icms_cst_normal = values.get('icms_cst_normal', False)
            line.icms_csosn_simples = values.get('icms_csosn_simples', False)
            line.icms_st_aliquota_mva = values.get('icms_st_aliquota_mva', False)
            line.aliquota_icms_proprio = values.get('aliquota_icms_proprio', False)
            line.incluir_ipi_base = values.get('incluir_ipi_base', False)
            line.icms_aliquota_reducao_base = values.get('icms_aliquota_reducao_base', False)
            line.icms_st_aliquota_reducao_base = values.get('icms_st_aliquota_reducao_base', False)
            line.ipi_cst = values.get('ipi_cst', False) or u'99'
            line.ipi_reducao_bc = values.get('ipi_reducao_bc', False)
            line.pis_cst = values.get('pis_cst', False)
            line.cofins_cst = values.get('cofins_cst', False)
            line.valor_bruto = line.qty * line.price_unit
            line.valor_desconto = line.valor_bruto * line.discount / 100
            taxes_ids = line.tax_ids.filtered(
                lambda tax: tax.company_id.id == line.order_id.
                company_id.id)
            fiscal_position_id = line.order_id.fiscal_position_id
            if fiscal_position_id:
                taxes_ids = fiscal_position_id.map_tax(
                    taxes_ids, line.product_id,
                    line.order_id.partner_id)
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            #ncm = line.product_id.fiscal_classification_id
            #line.fiscal_classification_id = ncm.id #line.product_id.fiscal_classification_id.code ncm
            taxes = {'taxes': []}
            if taxes_ids:
                ctx = line._prepare_tax_context()
                taxes_ids = taxes_ids.with_context(**ctx)
                taxes = taxes_ids.compute_all(price, currency, line.qty, product=line.product_id,
                                              partner=line.order_id.partner_id or False)
            for tax in taxes['taxes']:
                tax_id = self.env['account.tax'].browse(tax['id'])
                if tax_id.domain == 'icms':
                    line.valor_icms = tax.get('amount', 0.00)
                    line.base_icms = tax.get('base', 0.00)
                    line.aliquota_icms = tax_id.amount
                if tax_id.domain == 'pis':
                    line.valor_pis = tax.get('amount', 0.00)
                    line.base_pis = tax.get('base', 0.00)
                    line.aliquota_pis = tax_id.amount
                if tax_id.domain == 'cofins':
                    line.valor_cofins = tax.get('amount', 0.00)
                    line.base_cofins = tax.get('base', 0.00)
                    line.aliquota_cofins = tax_id.amount

    # Novos campos referentes ao imposto
    company_fiscal_type = fields.Selection(COMPANY_FISCAL_TYPE, default=_default_company_fiscal_type,
                                           string=u"Regime Tributário")
    cfop_id = fields.Many2one('br_account.cfop', string="CFOP")
    icms_cst = fields.Char('CST ICMS', size=10, store=True, compute='_compute_amount_line_all')
    icms_cst_normal = fields.Selection(CST_ICMS, string="CST ICMS", compute='_compute_amount_line_all')
    icms_csosn_simples = fields.Selection(CSOSN_SIMPLES, string="CSOSN ICMS", compute='_compute_amount_line_all')
    icms_st_aliquota_mva = fields.Float(string=u'Alíquota MVA (%)', digits=dp.get_precision('Account'))
    aliquota_icms_proprio = fields.Float(string=u'Alíquota ICMS Próprio (%)', digits=dp.get_precision('Account'))
    icms_aliquota_reducao_base = fields.Float(string=u'Redução Base ICMS (%)', digits=dp.get_precision('Account'))
    icms_st_aliquota_reducao_base = fields.Float(string=u'Redução Base ICMS ST(%)', digits=dp.get_precision('Account'))
    pis_cst = fields.Char(string='CST PIS', size=5)
    cofins_cst = fields.Char(string='CST COFINS', size=5)
    base_icms = fields.Float(string='Base ICMS', store=True, compute=_compute_amount_line_all)
    base_pis = fields.Float(string='Base PIS', store=True, compute=_compute_amount_line_all)
    base_cofins = fields.Float(string='Base COFINS', store=True, compute=_compute_amount_line_all)
    aliquota_icms = fields.Float()
    aliquota_pis = fields.Float()
    aliquota_cofins = fields.Float()

    # Classificação Fiscal do Produto
    fiscal_classification_id = fields.Many2one('product.fiscal.classification', u'Classificação Fiscal',
                                               related='product_id.fiscal_classification_id')

    # Novos campos referentes a valores
    #price_tax = fields.Float(compute='_compute_price', string='Impostos', store=True,
    #                         digits=dp.get_precision('Account'))
    #price_total = fields.Float(u'Valor Líquido', digits=dp.get_precision('Account'), store=True, default=0.00,
    #                           compute='_compute_price')
    valor_desconto = fields.Float(string='Vlr. Desc. (-)', store=True, digits=dp.get_precision('Sale Price'))
    valor_bruto = fields.Float(string='Vlr. Bruto', store=True, compute=_compute_amount_line_all,
                               digits=dp.get_precision('Sale Price'))
    valor_icms = fields.Float(string='Valor ICMS', store=True, digits=dp.get_precision('Sale Price'),
                              compute=_compute_amount_line_all)
    valor_pis = fields.Float(string='Valor PIS', store=True, digits=dp.get_precision('Sale Price'),
                             compute=_compute_amount_line_all)
    valor_cofins = fields.Float(string='Valor COFINS', store=True, digits=dp.get_precision('Sale Price'),
                                compute=_compute_amount_line_all)
