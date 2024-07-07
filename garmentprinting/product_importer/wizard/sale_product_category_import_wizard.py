import os
import io
from odoo import models, fields, api
import base64
import pandas as pd

class SaleProductCategoryImportWizard(models.TransientModel):
    _name = 'sale.product.category.import.wizard'
    _description = 'Wizard for importing product categories'

    database_attachment = fields.Binary(string='Database Attachment', required=True)

    #Import categories from all the products
    def import_categories(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0, dtype={'EAN': str})

            total_rows = len(df.index)
            for index, row in df.iterrows():
                if index % 300 == 0:
                    print(index, "PRODUCTOS IMPORTADOS DE", total_rows)
                    
