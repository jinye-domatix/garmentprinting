import os
import io
from odoo import models, fields, api
import base64
import pandas as pd
import logging
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class SaleProductImportWizard(models.TransientModel):
    _name = 'sale.product.import.wizard'
    _description = 'Wizard for Product Import from Excel'

    database_attachment = fields.Binary(string='Database Attachment', required=True)

    supplier_selector = fields.Selection([
        ('falkross', 'FalkRoss'),
        ('ralawise', 'Ralawise'),
        ('makito', 'Makito'),
    ], string='Supplier Selector', help='Choose an option', required=True)


    def import_product(self):
        if self.supplier_selector == 'falkross':
            self.import_products()
        elif self.supplier_selector == 'ralawise':
            self.import_products_ralawise()
        else:
            self.import_products_makito()

    # Import the products.template and create their variants
    def import_products(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0, dtype={'EAN': str, 'Article number short': str, 'Article number long': str})

            product_templates = {}
            total_rows = len(df.index)
            for index, row in df.iterrows():
                if index % 300 == 0:
                    _logger.debug(f"{index} IMPORTED PRODUCTS of {total_rows}")
                supplier = self.product_supplier(row)
                product_template = self.ensure_product_template(row, df, supplier)
                product_templates[product_template] = product_template
            self.assign_color_images(df)
            for product_template in product_templates:
                for product in product_template.product_variant_ids:
                    self.update_product_variant(product, df)
            self.product_exclusions(df, product_templates)

    def ensure_product_template(self, row, df, supplier):
        product_template = self.env['product.template'].search([('default_code', '=', row['Article number short'])], limit=1)

        if not product_template:
            filtered_df = df[df['Article number short'] == row['Article number short']]

            unique_colors = filtered_df['Color_Name'].unique()
            unique_sizes = filtered_df['Size_Description'].unique()

            color_value_ids = [self.get_or_create_attribute_value('Color', color) for color in unique_colors]
            size_value_ids = [self.get_or_create_attribute_value('Size', size) for size in unique_sizes]

            product_template = self.env['product.template'].create({
                'short_article_number': row['Article number short'],
                'default_code': row['Article number short'],
                'name': row['Article_name'],
                'attribute_line_ids': [
                    (0, 0, {'attribute_id': self.get_attribute_id('Color'), 'value_ids': [(6, 0, color_value_ids)]}),
                    (0, 0, {'attribute_id': self.get_attribute_id('Size'), 'value_ids': [(6, 0, size_value_ids)]})
                ]
            })

            self.env['product.supplierinfo'].create({
                'product_tmpl_id': product_template.id,
                'partner_id': supplier.id,
                'price': row['Customer_price /1-148/']
            })

            product_template._create_variant_ids()
        return product_template

    def get_or_create_attribute_value(self, attribute_name, value):
        attribute_id = self.get_attribute_id(attribute_name)
        attribute_value = self.env['product.attribute.value'].search([('attribute_id', '=', attribute_id), ('name', '=', value)], limit=1)
        if not attribute_value:
            attribute_value = self.env['product.attribute.value'].create({'attribute_id': attribute_id, 'name': value})
        return attribute_value.id

    def get_attribute_id(self, attribute_name):
        attribute = self.env['product.attribute'].search([('name', '=', attribute_name)], limit=1)
        if not attribute:
            if attribute_name == "Color":
                attribute = self.env['product.attribute'].create({
                    'name': attribute_name,
                    'display_type': 'color'
                })
            else:
                attribute = self.env['product.attribute'].create({
                    'name': attribute_name,
                    'display_type': 'select'
                })
        return attribute.id

    def product_supplier(self, row):
        country_code = row['Country of Origin']
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if not country:
            _logger.debug(f"No se encontró el país con código: {country_code}")
            return None
        supplier = self.env['res.partner'].search([('name', '=', row['Supplier_Name'])], limit=1)
        if not supplier:
            supplier = self.env['res.partner'].create({
                'name': row['Supplier_Name'],
                'is_company': True,
                'country_id': country.id
            })
        return supplier

    def assign_color_images(self, df):
        attribute_color = self.env['product.attribute'].search([('name', '=', 'Color')])
        if not attribute_color:
            _logger.debug("Attribute 'Color' not found.")
            return

        for value in attribute_color.value_ids:
            if value.image:
                _logger.debug(f"El color '{value.name}' ya tiene imagen asignada. Se omite.")
                continue
            image_path = df[df['Color_Name'] == value.name]['Pictogram'].values[0] if len(df[df['Color_Name'] == value.name]['Pictogram'].values) > 0 else None
            if not image_path:
                _logger.debug(f"No se encontró el path de imagen para: {value.name}")
                continue
            full_path = None
            try:
                full_path = file_path(f'product_importer/data/Piktogramme/{image_path}')
            except FileNotFoundError:
                _logger.debug(f"No se encontró el archivo de imagen para: {value.name} en {full_path}")
                continue
            if not os.path.exists(full_path):
                _logger.debug(f"No se encontró el archivo de imagen para: {value.name} en {full_path}")
                continue

            encoded_image = self.encode_image(full_path)
            if encoded_image:
                value.write({'image': encoded_image})
                _logger.debug(f"Imagen asignada al valor de color '{value.name}'.")
            else:
                _logger.debug(f"No se pudo codificar la imagen para el color '{value.name}'.")

    def encode_image(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                _logger.debug(f"Image successfully encoded for {image_path}")
                return encoded_image
        except Exception as e:
            _logger.debug(f"Failed to encode image at {image_path}: {e}")
            return False

    # Add all attributes to each products.product
    def update_product_variant(self, product, df):
        Article_name = product.name
        color_name = product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Color').product_attribute_value_id.name if product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Color') else 'Unknown Color'
        size_name = product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Size').product_attribute_value_id.name if product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Size') else 'Unknown Size'
        _logger.debug(f"Updating product: {product.id}, Name: {Article_name}, Color: {color_name}, Size: {size_name}")

        matching_rows = df[(df['Article_name'] == Article_name) &
                           (df['Color_Name'] == color_name) &
                           (df['Size_Description'] == size_name)]

        _logger.debug(f"Searching for: Article_name: {Article_name}, Color_Name: {color_name}, Size_Description: {size_name}")
        _logger.debug(f"Matching rows found: {len(matching_rows)}")
        if not matching_rows.empty:
            _logger.debug(f"Found row for product: {product.id}")
            self.update_variant(product, matching_rows.iloc[0])
        else:
            _logger.debug(f"No row found for product: {product.id}")

    def update_variant(self, variant, row):
        _logger.debug(f"Updating variant fields for: {variant.id}")
        weight_in_grams = float(row['Weight']) / 1000.0
        barcode_value = row['EAN'] if pd.notna(row['EAN']) else None

        if self.env['product.product'].search([('barcode', '=', barcode_value)]):
            _logger.debug(f"Barcode {barcode_value} already exists in the system.")
            barcode_value = None

        variant.write({
            'default_code': row['Article number long'],
            'weight': weight_in_grams,
            'lst_price': row['Customer_price /1-148/'],
            'supplier_article_code': row['Supplier_Article_Code'],
            'barcode': barcode_value,
            'description': row['Article_description']
        })

    # Excludes color and size combinations
    def product_exclusions(self, df, product_templates):
        product_templates = list(product_templates)

        # Agrupar todas las búsquedas iniciales
        product_attributes = self.env['product.template.attribute.value'].search([
            ('product_tmpl_id', 'in', [pt.id for pt in product_templates])
        ])
        attribute_lines = self.env['product.template.attribute.line'].search([
            ('product_tmpl_id', 'in', [pt.id for pt in product_templates])
        ])

        for template in product_templates:
            # Filtrar las líneas de atributo relevantes
            template_lines = attribute_lines.filtered(lambda l: l.product_tmpl_id.id == template.id)
            all_sizes = template_lines.filtered(lambda l: l.attribute_id.display_name == 'Size').mapped('value_ids')
            all_size_names = set(size.name for size in all_sizes)
            all_colors = template_lines.filtered(lambda l: l.attribute_id.display_name == 'Color').mapped('value_ids')

            for color in all_colors:
                product_df = df[df['Article_name'] == template.name]
                color_df = product_df[product_df['Color_Name'] == color.name]

                if color_df.empty:
                    _logger.debug(f"No data found for color {color.name} in product {template.name}")
                    continue

                color_sizes = set(color_df['Size_Description'].dropna())
                available_size_names = set(color_sizes)

                sizes_to_exclude = all_size_names - available_size_names
                _logger.debug(f"All sizes: {all_size_names}")
                _logger.debug(f"Available sizes for {color.name}: {available_size_names}")
                _logger.debug(f"Sizes to exclude for {color.name}: {sizes_to_exclude}")

                if not sizes_to_exclude:
                    _logger.debug(f"No sizes to exclude for color {color.name} in product {template.name}")
                    continue

                color_attribute = product_attributes.filtered(
                    lambda v: v.product_tmpl_id.id == template.id and v.name == color.name)
                if not color_attribute:
                    _logger.debug(f"No attribute value found for color {color.name} in template {template.name}")
                    continue

                value_ids = []
                for size_name in sizes_to_exclude:
                    size_attribute = product_attributes.filtered(
                        lambda v: v.product_tmpl_id.id == template.id and v.name == size_name)
                    if size_attribute:
                        value_ids.append(size_attribute.id)

                if value_ids:
                    self.env['product.template.attribute.exclusion'].create({
                        'product_tmpl_id': template.id,
                        'product_template_attribute_value_id': color_attribute.id,
                        'value_ids': [(6, 0, value_ids)]
                    })
                    _logger.debug(
                        f"Exclusion created for color {color.name} with missing sizes in product {template.name}")

            template._create_variant_ids()
        return True
    
    # RALAWISE
    # Import the products.template and create their variants
    def import_products_ralawise(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0, dtype={'ProductGroup': str, 'SkuCode': str, 'ColourNmae': str, 'SizeCode': str, 'CustCartonPrice': str, 'ProductName': str})

            product_templates = {}
            total_rows = len(df.index)
            for index, row in df.iterrows():
                if index % 300 == 0:
                    _logger.debug(f"{index} IMPORTED PRODUCTS of {total_rows}")
                product_template = self.ensure_product_template_ralawise(row, df)
                product_templates[product_template] = product_template
            for product_template in product_templates:
                for product in product_template.product_variant_ids:
                    self.update_product_variant_ralawise(product, df)
            self.product_exclusions_ralawise(df, product_templates)
               
    def ensure_product_template_ralawise(self, row, df):
        product_template = self.env['product.template'].search([('default_code', '=', row['ProductGroup'])], limit=1)

        if not product_template:
            filtered_df = df[df['ProductGroup'] == row['ProductGroup']]

            unique_colors = filtered_df['ColourName'].unique()
            unique_sizes = filtered_df['SizeCode'].unique()

            color_value_ids = [self.get_or_create_attribute_value_ralawise('Color', color) for color in unique_colors]
            size_value_ids = [self.get_or_create_attribute_value_ralawise('Size', size) for size in unique_sizes]

            product_template = self.env['product.template'].create({
                'short_article_number': row['ProductGroup'],
                'default_code': row['ProductGroup'],
                'name': row['ProductName'],
                'attribute_line_ids': [
                    (0, 0, {'attribute_id': self.get_attribute_id_ralawise('Color'), 'value_ids': [(6, 0, color_value_ids)]}),
                    (0, 0, {'attribute_id': self.get_attribute_id_ralawise('Size'), 'value_ids': [(6, 0, size_value_ids)]})
                ]
            })
            self.env.cr.commit()

            product_template._create_variant_ids()
        return product_template

    def get_or_create_attribute_value_ralawise(self, attribute_name, value):
        attribute_id = self.get_attribute_id_ralawise(attribute_name)
        value_str = str(value)
        attribute_value = self.env['product.attribute.value'].search([('attribute_id', '=', attribute_id), ('name', '=', value_str)], limit=1)
        if not attribute_value:
            attribute_value = self.env['product.attribute.value'].create({'attribute_id': attribute_id, 'name': value_str})
        return attribute_value.id

    def get_attribute_id_ralawise(self, attribute_name):
        attribute = self.env['product.attribute'].search([('name', '=', attribute_name)], limit=1)
        if not attribute:
            if attribute_name == "Color":
                attribute = self.env['product.attribute'].create({
                    'name': attribute_name,
                    'display_type': 'color'
                })
                self.env.cr.commit()
            else:
                attribute = self.env['product.attribute'].create({
                    'name': attribute_name,
                    'display_type': 'select'
                })
                self.env.cr.commit()
        return attribute.id

    # Add all attributes to each products.product
    def update_product_variant_ralawise(self, product, df):
        Article_name = product.name
        color_name = product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Color').product_attribute_value_id.name if product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Color') else 'Unknown Color'
        size_name = product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Size').product_attribute_value_id.name if product.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.name == 'Size') else 'Unknown Size'
        _logger.debug(f"Updating product: {product.id}, Name: {Article_name}, Color: {color_name}, Size: {size_name}")

        matching_rows = df[(df['ProductName'] == Article_name) &
                        (df['ColourName'] == color_name) &
                        (df['SizeCode'] == size_name)]

        _logger.debug(f"Searching for: Article_name: {Article_name}, Color_Name: {color_name}, Size_Description: {size_name}")
        _logger.debug(f"Matching rows found: {len(matching_rows)}")
        if not matching_rows.empty:
            _logger.debug(f"Found row for product: {product.id}")
            self.update_variant_ralawise(product, matching_rows.iloc[0])
        else:
            _logger.debug(f"No row found for product: {product.id}")

    def update_variant_ralawise(self, variant, row):
        _logger.debug(f"Updating variant fields for: {variant.id}")
        variant.write({
            'default_code': row['SkuCode'],
            'lst_price': row['CustCartonPrice'],
            'description': row['Specification'],
            'brand': row['Brand']
        })
        self.env.cr.commit()

    # Excludes color and size combinations
    def product_exclusions_ralawise(self, df, product_templates):
        product_templates = list(product_templates)

        product_attributes = self.env['product.template.attribute.value'].search([
            ('product_tmpl_id', 'in', [pt.id for pt in product_templates])
        ])
        attribute_lines = self.env['product.template.attribute.line'].search([
            ('product_tmpl_id', 'in', [pt.id for pt in product_templates])
        ])

        for template in product_templates:
            template_lines = attribute_lines.filtered(lambda l: l.product_tmpl_id.id == template.id)
            all_sizes = template_lines.filtered(lambda l: l.attribute_id.display_name == 'Size').mapped('value_ids')
            all_size_names = set(size.name for size in all_sizes)
            all_colors = template_lines.filtered(lambda l: l.attribute_id.display_name == 'Color').mapped('value_ids')

            for color in all_colors:
                product_df = df[df['ProductName'] == template.name]
                color_df = product_df[product_df['ColourName'] == color.name]

                if color_df.empty:
                    _logger.debug(f"No data found for color {color.name} in product {template.name}")
                    continue

                color_sizes = set(color_df['SizeCode'].dropna())
                available_size_names = set(color_sizes)

                sizes_to_exclude = all_size_names - available_size_names
                _logger.debug(f"All sizes: {all_size_names}")
                _logger.debug(f"Available sizes for {color.name}: {available_size_names}")
                _logger.debug(f"Sizes to exclude for {color.name}: {sizes_to_exclude}")

                if not sizes_to_exclude:
                    _logger.debug(f"No sizes to exclude for color {color.name} in product {template.name}")
                    continue

                color_attribute = product_attributes.filtered(
                    lambda v: v.product_tmpl_id.id == template.id and v.name == color.name)
                if not color_attribute:
                    _logger.debug(f"No attribute value found for color {color.name} in template {template.name}")
                    continue

                value_ids = []
                for size_name in sizes_to_exclude:
                    size_attribute = product_attributes.filtered(
                        lambda v: v.product_tmpl_id.id == template.id and v.name == size_name)
                    if size_attribute:
                        value_ids.append(size_attribute.id)

                if value_ids:
                    self.env['product.template.attribute.exclusion'].create({
                        'product_tmpl_id': template.id,
                        'product_template_attribute_value_id': color_attribute.id,
                        'value_ids': [(6, 0, value_ids)]
                    })
                    self.env.cr.commit()
                    _logger.debug(
                        f"Exclusion created for color {color.name} with missing sizes in product {template.name}")

            template._create_variant_ids()
        return True