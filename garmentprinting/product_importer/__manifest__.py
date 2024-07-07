# Copyright <YEAR(S)> <AUTHOR(S)>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "garmentprinting",
    "summary": "",
    "version": "17.0.1.0.0",
    "category": "",
    "author": "<German Lopez Avila>, Domatix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "sale","web","base","portal","product","sale_management"
    ],

    "data": ["views/sale_views.xml",
             "views/product_views.xml",
             "wizard/sale_product_import_wizard.xml",
             "wizard/sale_product_category_import_wizard.xml",
             "wizard/sale_product_image_import_wizard.xml",
             "wizard/sale_product_language_import_wizard.xml",
             "security/ir.model.access.csv",
             ]
}