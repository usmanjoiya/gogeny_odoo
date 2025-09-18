from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_reference = fields.Char(
        string="ID Number",
        help="Unique reference or code for this customer."
    )
    project_line_ids = fields.One2many('res.partner.project.line', 'partner_id', string="Projects & Payment Terms")
    _sql_constraints = [
        (
            'unique_customer_reference',
            'unique(customer_reference)',
            'The Customer Reference must be unique.'
        )
    ]


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
