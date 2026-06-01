import uuid
import xml.etree.ElementTree as ET
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, State, MATCH, ALL, ctx, no_update

import ocads_unified_components
from utils import read_existing, save_existing, TEMP_XML_FILE, NS_URL

class MetadataListGroup(html.Div):
    def __init__(self, list_field_name, component_class, instance_id='default', className=None, **kwargs):
        self.list_field_name = list_field_name
        self.component_class = component_class
        self.base_instance = instance_id
        self.list_token = f"list-{list_field_name}-{instance_id}"

        display_label = list_field_name.replace('_', ' ').title()
        class_name_string = component_class.__name__ if hasattr(component_class, '__name__') else 'Div'

        # 🎯 THE HYDRATION BLOCK: Crawl the file to compile and render existing entries on load
        existing_cards = []
        try:
            root = read_existing(TEMP_XML_FILE)

            # Map structural collection plural tags to match the callback rules
            parent_plural_tag = "cited_authors" if list_field_name == "author" else f"{list_field_name}s"
            if list_field_name in ['basic', 'observed', 'DIC', 'TA', 'pH', 'co2_discrete', 'co2_continuous']:
                parent_plural_tag = "variables"

            parent_plural_node = root.find(f".//{{{NS_URL}}}{parent_plural_tag}")
            if parent_plural_node is not None:
                for idx, item_node in enumerate(parent_plural_node.findall(f"./{{{NS_URL}}}{list_field_name}")):
                    # Safely extract or establish unique tracking row tokens
                    row_hash = item_node.get("row_token")
                    if not row_hash:
                        row_hash = uuid.uuid4().hex[:6].upper()
                        item_node.set("row_token", row_hash)
                        save_existing(TEMP_XML_FILE, root)

                    row_id_string = f"{instance_id}_row_{row_hash}"
                    summary_text = f"{list_field_name.title()} entry #{row_hash}"

                    # Isolate descriptive string fields for array list elements
                    if class_name_string in ['Div', 'html.Div', '']:
                        if item_node.text:
                            summary_text = item_node.text.strip()
                    else:
                        # Extract the best possible text identifier from standard nested sub-elements
                        for target_tag in ['name', 'title', 'package_name', 'first', 'last']:
                            found_el = item_node.find(f".//{{{NS_URL}}}{target_tag}")
                            if found_el is not None and found_el.text:
                                summary_text = found_el.text.strip()
                                break

                    # Programmatically generate matching interactive control item rows
                    card = dbc.Alert([
                        html.Span(summary_text, className="fw-bold me-3"),
                        html.Div([
                            dbc.Button("✏️ Edit", id={'type': 'list-edit-row-btn', 'list_token': self.list_token, 'row_token': row_id_string}, size="sm", color="light", className="me-1"),
                            dbc.Button("❌ Delete", id={'type': 'list-delete-row-btn', 'list_token': self.list_token, 'row_token': row_id_string}, size="sm", color="danger")
                        ], className="float-end", style={"marginTop": "-5px"})
                    ], color="info", className="mb-2 clearfix", id={'type': 'alert-row-item', 'token': row_id_string})
                    existing_cards.append(card)
        except Exception:
            pass  # Fall back safely if file nodes are un-initialized

        # If no entries live in the workspace file yet, swap in the standard empty hint row layout
        if not existing_cards:
            existing_cards = [html.P(f"No {list_field_name} entries added yet.", className="text-muted small italic", id={'type': 'empty-placeholder', 'list_token': self.list_token})]

        layout = [
            html.Div([
                html.H6(f"Managed {display_label} List Entries", className='fw-bold text-dark mb-2'),
                html.Div(
                    id={'type': 'list-summary-display', 'list_token': self.list_token},
                    children=existing_cards,  # ✅ FIXED: Mounts pre-existing cards instantly on page creation
                    className="p-2 border rounded bg-white mb-2"
                ),
                dbc.Button(f"➕ Add New {display_label}", id={'type': 'list-open-modal-btn', 'list_token': self.list_token}, color="primary", size="sm")
            ]),
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(f"Configure {display_label} Details")),
                dbc.ModalBody(id={'type': 'list-modal-body', 'list_token': self.list_token}),
                dbc.ModalFooter([
                    dbc.Button("Cancel", id={'type': 'list-close-modal-btn', 'list_token': self.list_token}, color="light"),
                    dbc.Button("Save Item", id={'type': 'list-save-item-btn', 'list_token': self.list_token}, color="success")
                ])
            ], id={'type': 'list-modal-wrapper', 'list_token': self.list_token}, is_open=False, size="lg"),

            dcc.Store(
                id={'type': 'list-metadata-store', 'list_token': self.list_token},
                data={
                    'list_field_name': list_field_name,
                    'class_name_string': class_name_string,
                    'base_instance': instance_id,
                    'active_editing_row_id': None,
                    'list_token': self.list_token
                }
            )
        ]
        default_class = 'p-3 border rounded mb-4 bg-light shadow-sm'
        combined_class = f'{default_class} {className}' if className else default_class
        super().__init__(children=layout, className=combined_class, **kwargs)

@callback(
    Output({'type': 'list-modal-wrapper', 'list_token': MATCH}, 'is_open'),
    Output({'type': 'list-modal-body', 'list_token': MATCH}, 'children'),
    Output({'type': 'list-metadata-store', 'list_token': MATCH}, 'data'),

    Input({'type': 'list-open-modal-btn', 'list_token': MATCH}, 'n_clicks'),
    Input({'type': 'list-close-modal-btn', 'list_token': MATCH}, 'n_clicks'),
    Input({'type': 'list-save-item-btn', 'list_token': MATCH}, 'n_clicks'),
    Input({'type': 'list-edit-row-btn', 'list_token': MATCH, 'row_token': ALL}, 'n_clicks'),

    State({'type': 'list-metadata-store', 'list_token': MATCH}, 'data'),
    prevent_initial_call=True
)
def handle_list_modal_lifecycle(add_clicks, close_clicks, save_clicks, edit_clicks_list, current_config):
    if not ctx.triggered or ctx.triggered[0]['value'] in [0, None]:
        return no_update, no_update, no_update

    triggered_id = ctx.triggered_id
    trigger_type = triggered_id.get('type')
    class_name = current_config['class_name_string']
    list_field_name = current_config['list_field_name']

    if trigger_type in ['list-open-modal-btn', 'list-edit-row-btn']:
        if trigger_type == 'list-open-modal-btn':
            new_row_hash = uuid.uuid4().hex[:6].upper()
            row_id_string = f"{current_config['base_instance']}_row_{new_row_hash}"
            row_data = {}
        else:
            row_id_string = triggered_id['row_token']
            row_hash = row_id_string.split("_row_")[-1]
            row_data = {}

            root = read_existing(TEMP_XML_FILE)
            item_node = root.find(f".//*[@row_token='{row_hash}']")
            if item_node is not None:
                def clean_tag(t): return t.split('}')[-1]
                if len(item_node) == 0 and item_node.text:
                    row_data.setdefault(list_field_name, {})[list_field_name] = item_node.text
                else:
                    parent_map = {c: p for p in item_node.iter() for c in p}
                    for child in item_node.iter():
                        if len(child) == 0 and child.text:
                            p_node = parent_map.get(child)
                            p_tag = clean_tag(p_node.tag) if p_node is not None else clean_tag(item_node.tag)
                            row_data.setdefault(p_tag, {})[clean_tag(child.tag)] = child.text

        if class_name in ['Div', 'html.Div', '']:
            display_label = list_field_name.replace('_', ' ').title()
            form_layout = dbc.Row([
                dbc.Label(f"{display_label} Text Value", width=4, className='text-muted small fw-bold'),
                dbc.Col([
                    dbc.Input(
                        id={'type': 'primitive-input', 'complex-type': list_field_name, 'field': list_field_name, 'instance': row_id_string},
                        type='text',
                        value=row_data.get(list_field_name, {}).get(list_field_name, ""),
                        placeholder=f"Enter {display_label} string text entry..."
                    )
                ], width=8)
            ], className='mb-2 p-3')
        else:
            class_obj = getattr(ocads_unified_components, class_name)
            form_layout = class_obj(instance_id=row_id_string, initial_values=row_data)

        current_config['active_editing_row_id'] = row_id_string
        return True, form_layout, current_config

    return False, html.Div(), current_config

@callback(
    Output({'type': 'list-summary-display', 'list_token': MATCH}, 'children'),
    Input({'type': 'list-save-item-btn', 'list_token': MATCH}, 'n_clicks'),
    Input({'type': 'list-delete-row-btn', 'list_token': MATCH, 'row_token': ALL}, 'n_clicks'),

    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'id'),
    State({'type': 'list-metadata-store', 'list_token': MATCH}, 'data'),
    State({'type': 'list-summary-display', 'list_token': MATCH}, 'children'),
    prevent_initial_call=True
)
def sync_list_item_data_to_redis_and_ui(save_clicks, delete_clicks, form_vals, form_ids, config, current_summary_elements):
    trigger = ctx.triggered_id
    if not trigger: return no_update

    root = read_existing(TEMP_XML_FILE)
    list_element_name = config['list_field_name']

    parent_plural_tag = "cited_authors" if list_element_name == "author" else f"{list_element_name}s"
    if list_element_name in ['basic', 'observed', 'DIC', 'TA', 'pH', 'co2_discrete', 'co2_continuous']:
        parent_plural_tag = "variables"

    parent_plural_node = root.find(f".//{{{NS_URL}}}{parent_plural_tag}")
    if parent_plural_node is None:
        parent_plural_node = ET.SubElement(root, f"{{{NS_URL}}}{parent_plural_tag}")

    if trigger.get('type') == 'list-save-item-btn':
        target_row_id = config['active_editing_row_id']
        row_hash = target_row_id.split("_row_")[-1]

        item_node = parent_plural_node.find(f"./{{{NS_URL}}}{list_element_name}[@row_token='{row_hash}']")
        if item_node is None:
            item_node = ET.SubElement(parent_plural_node, f"{{{NS_URL}}}{list_element_name}", {"row_token": row_hash})

        summary_text = f"{list_element_name.title()} entry #{row_hash}"

        for val, identity in zip(form_vals, form_ids):
            if identity['instance'] == target_row_id:
                f_name = identity['field']
                p_tag = identity['complex-type']

                if val:
                    if f_name in ['name', 'title', 'package_name', 'first', 'last'] or p_tag == list_element_name:
                        summary_text = str(val)

                if p_tag == list_element_name and f_name == list_element_name:
                    item_node.text = str(val) if val is not None else ""
                else:
                    target_container = item_node
                    if p_tag != list_element_name:
                        xml_container_tag = "country" if p_tag == "vocabulary_item_reference" else p_tag
                        xml_container_tag = "identifier" if p_tag == "typed_identifier" else xml_container_tag

                        target_container = item_node.find(f".//{{{NS_URL}}}{xml_container_tag}")
                        if target_container is None:
                            target_container = ET.SubElement(item_node, f"{{{NS_URL}}}{xml_container_tag}")

                    child_node = target_container.find(f"./{{{NS_URL}}}{f_name}")
                    if child_node is None:
                        child_node = ET.SubElement(target_container, f"{{{NS_URL}}}{f_name}")
                    child_node.text = str(val) if val is not None else ""

        save_existing(TEMP_XML_FILE, root)

        new_card = dbc.Alert([
            html.Span(summary_text, className="fw-bold me-3"),
            html.Div([
                dbc.Button("✏️ Edit", id={'type': 'list-edit-row-btn', 'list_token': config['list_token'], 'row_token': target_row_id}, size="sm", color="light", className="me-1"),
                dbc.Button("❌ Delete", id={'type': 'list-delete-row-btn', 'list_token': config['list_token'], 'row_token': target_row_id}, size="sm", color="danger")
            ], className="float-end", style={"marginTop": "-5px"})
        ], color="info", className="mb-2 clearfix", id={'type': 'alert-row-item', 'token': target_row_id})

        cleaned_elements = [el for el in current_summary_elements if el['props'].get('id', {}).get('type') != 'empty-placeholder']
        existing_idx = next((i for i, el in enumerate(cleaned_elements) if el['props'].get('id', {}).get('token') == target_row_id), None)
        if existing_idx is not None:
            cleaned_elements[existing_idx] = new_card
        else:
            cleaned_elements.append(new_card)
        return cleaned_elements

    elif trigger.get('type') == 'list-delete-row-btn':
        target_row_id = trigger['row_token']
        row_hash = target_row_id.split("_row_")[-1]

        item_node = parent_plural_node.find(f"./{{{NS_URL}}}{list_element_name}[@row_token='{row_hash}']")
        if item_node is not None:
            parent_plural_node.remove(item_node)
            save_existing(TEMP_XML_FILE, root)

        updated_elements = [el for el in current_summary_elements if el['props'].get('id', {}).get('token') != target_row_id]
        if not updated_elements:
            return [html.P(f"No {list_element_name} entries added yet.", className="text-muted small italic", id={'type': 'empty-placeholder', 'list_token': config['list_token']})]
        return updated_elements

    return current_summary_elements