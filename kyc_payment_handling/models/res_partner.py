from odoo import models, fields, api
from odoo.exceptions import ValidationError

MAIN_COMPANY_NAME = 'Gogenie'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_reference = fields.Char(
        string="ID Number",
        help="Unique reference or code for this customer."
    )
    portal_password = fields.Char(string="Portal Password")
    project_line_ids = fields.One2many('res.partner.project.line', 'partner_id', string="Projects & Payment Terms")
    _sql_constraints = [
        (
            'unique_customer_reference',
            'unique(customer_reference)',
            'The Customer Reference must be unique.'
        )
    ]

    def _ensure_main_company_on_linked_users(self):
        main_company = self.env['res.company'].sudo().search(
            [('name', '=', MAIN_COMPANY_NAME)], limit=1
        )
        if not main_company:
            return
        for partner in self:
            if not partner.company_id or partner.company_id == main_company:
                continue
            users = self.env['res.users'].sudo().search([('partner_id', '=', partner.id)])
            users_missing = users.filtered(lambda u: main_company not in u.company_ids)
            if users_missing:
                users_missing.sudo().write({'company_ids': [(4, main_company.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._ensure_main_company_on_linked_users()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'company_id' in vals:
            self._ensure_main_company_on_linked_users()
        return res



class PartnerProjectLine(models.Model):
    _name = 'res.partner.project.line'
    _description = "Partner's Projects and Payment Terms"

    partner_id = fields.Many2one('res.partner', string="Partner", required=True, ondelete='cascade')
    product_id = fields.Many2one("product.template", required=True)
    project_id = fields.Many2one('project.project', string="Project", required=True)
    payment_term_id = fields.Many2one('account.payment.term', string="Payment Term", required=True)
    state = fields.Selection(
        related="project_id.state",
        store=True,
        readonly=True,
        string="Project State"
    )
