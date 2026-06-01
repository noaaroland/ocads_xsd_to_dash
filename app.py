import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Output, Input, State, callback, ctx, ALL, MATCH, no_update
import xml.etree.ElementTree as ET
import ocads_unified_components_v3
from ocads_unified_components import *

import dash_ag_grid as dag
from metadata_ref_selector import MetadataRefSelector
from metadata_list_group import MetadataListGroup

import uuid
from utils import read_existing, save_existing, NS_URL, TEMP_XML_FILE, get_all_entities_from_xml
from ocads_submit import MetadataSubmitButton

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    html.H1("OCADS Metadata Submission Form Wizard", className="my-4"),
    Person(instance_id="TEST_OF_SUBMIT_BUTTON"),
    CrmInfo(instance_id="TEST_OF_SUBMIT_BUTTON"),
    SensorRawDataConversion(instance_id="TEST_OF_SUBMIT_BUTTON"),

    MetadataSubmitButton(
        instance_id="TEST_OF_SUBMIT_BUTTON",
        targets=['crm_info', "sensor_raw_data_conversion", "software_info"],
        label="Save Conversion Specification Data",
        color="success"
    ),
    MeasuredVarInfo(instance_id="variable_dic_sample"),

    MetadataSubmitButton(
        instance_id="variable_dic_sample",
        targets=["measured_var_info", "sensor_raw_data_conversion", "software_info"],
        label="Commit Comprehensive Variable Metrics",
        color="dark"
    ),

    MetadataRefSelector(
        ref_field_name="data_submitter",
        target_class="PersonDefinition",
        instance_id="dataset_cruise_sheet"
    ),

    MetadataSubmitButton(
        instance_id="dataset_cruise_sheet",
        targets=["data_submitter_ref"],
        label="Confirm Primary Submitter Selection"
    ),

    # The dynamic list group manages its own internal modal states seamlessly
    MetadataListGroup(
        list_field_name="platform",
        component_class=Platform,
        instance_id="cruise_2026_dataset"
    )
], fluid=True)


@callback(
    Output({'type': 'metadata-submit', 'instance': ALL, 'targets': ALL}, 'disabled'),
    Input({'type': 'metadata-submit', 'instance': ALL, 'targets': ALL}, 'n_clicks'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'id'),
    prevent_initial_call=True
)
def handle_form_submission(n_clicks_list, form_values, form_ids):
    if not ctx.triggered or ctx.triggered[0]['value'] in (0, None):
        return [dash.no_update] * len(n_clicks_list)

    triggered_id = ctx.triggered_id
    active_instance = triggered_id['instance']
    active_targets = triggered_id['targets'].split(',')

    submission_payload = {}
    for value, identity in zip(form_values, form_ids):
        if identity['instance'] == active_instance and identity['complex-type'] in active_targets:
            c_type = identity['complex-type']
            field = identity['field']
            submission_payload.setdefault(c_type, {})[field] = value

    if not submission_payload:
        return [dash.no_update] * len(n_clicks_list)

    root = read_existing(TEMP_XML_FILE)

    for complex_type, fields in submission_payload.items():
        parent_node = root.find(f".//{{{NS_URL}}}{complex_type}")
        if parent_node is None:
            parent_node = ET.SubElement(root, f"{{{NS_URL}}}{complex_type}")

        parent_node.set("object_id", active_instance)

        for field_name, field_value in fields.items():
            child_node = parent_node.find(f"{{{NS_URL}}}{field_name}")
            if child_node is None:
                child_node = ET.SubElement(parent_node, field_name)
            child_node.text = str(field_value) if field_value is not None else ""

    save_existing(TEMP_XML_FILE, root)
    return [dash.no_update] * len(n_clicks_list)


@callback(
    Output({'type': 'primitive-input', 'complex-type': ALL, 'field': 'object_id', 'instance': ALL}, 'value'),
    Input({'type': 'ref-grid', 'field_name': ALL, 'instance': ALL}, 'selectedRows'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': 'object_id', 'instance': ALL}, 'id'),
    prevent_initial_call=True
)
def bind_grid_selection_to_input(selected_rows_list, input_ids):
    if not ctx.triggered or ctx.triggered[0]['value'] is None:
        return [no_update] * len(input_ids)

    # 1. Capture the structural dict tracking key from the trigger event
    triggered_grid = ctx.triggered_id

    # 2. Trace the exact item array order using ctx.inputs_list to find the index integer
    grid_index = None
    for idx, input_item in enumerate(ctx.inputs_list[0]):
        if input_item['id'] == triggered_grid:
            grid_index = idx
            break

    # Guard check in case layout states do not align cleanly
    if grid_index is None:
        return [no_update] * len(input_ids)

    # 3. Now grid_index is safely an integer, extracting data row values works perfectly
    selected = selected_rows_list[grid_index]
    chosen_id = selected[0]['object_id'] if selected else ""

    outputs = []
    for identity in input_ids:
        # Check if the input element ends with '_ref' and shares the target instance context
        if (identity['instance'] == triggered_grid['instance'] and
                str(identity['complex-type']).endswith('_ref') and
                identity['complex-type'].startswith(triggered_grid['field_name'])):
            outputs.append(chosen_id)
        else:
            outputs.append(no_update)

    return outputs


@callback(
    Output({'type': 'ref-modal', 'field_name': MATCH, 'instance': MATCH}, 'is_open'),
    Output({'type': 'modal-body-form', 'field_name': MATCH, 'instance': MATCH}, 'children'),
    Input({'type': 'open-modal-btn', 'field_name': MATCH, 'instance': MATCH}, 'n_clicks'),
    Input({'type': 'close-modal-btn', 'field_name': MATCH, 'instance': MATCH}, 'n_clicks'),
    Input({'type': 'save-entity-btn', 'field_name': MATCH, 'instance': MATCH}, 'n_clicks'),
    State({'type': 'ref-modal', 'field_name': MATCH, 'instance': MATCH}, 'is_open'),
    prevent_initial_call=True
)
def toggle_and_populate_modal(open_btn, close_btn, save_btn, is_open):
    if not ctx.triggered or ctx.triggered[0]['value'] in [0, None]:
        return no_update, no_update

    triggered_element_type = ctx.triggered_id['type']

    if triggered_element_type == 'open-modal-btn' and not is_open:
        field_name = ctx.triggered_id['field_name']
        parent_instance = ctx.triggered_id['instance']
        new_entity_id = f"ID_{uuid.uuid4().hex[:8].upper()}"

        if "contact" in field_name or "submitter" in field_name or "author" in field_name:
            form_child = PersonDefinition(instance_id=new_entity_id)
        else:
            form_child = OrganizationDefinition(instance_id=new_entity_id)

        container = html.Div([
            form_child,
            dcc.Store(
                id={'type': 'active-modal-entity-id', 'field_name': field_name, 'instance': parent_instance},
                data=new_entity_id
            )
        ])
        return True, container

    return False, dash.no_update


@callback(
    Output({'type': 'ref-grid', 'field_name': MATCH, 'instance': MATCH}, 'rowData'),
    Input({'type': 'save-entity-btn', 'field_name': MATCH, 'instance': MATCH}, 'n_clicks'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'id'),
    State({'type': 'active-modal-entity-id', 'field_name': MATCH, 'instance': MATCH}, 'data'),
    prevent_initial_call=True
)
def commit_new_entity_definition(save_clicks, form_values, form_ids, active_modal_entity_id):
    if not save_clicks or not active_modal_entity_id:
        return dash.no_update

    field_name = ctx.triggered_id['field_name']
    is_person = "contact" in field_name or "submitter" in field_name or "author" in field_name

    collection_name = "people" if is_person else "organizations"
    element_tag = "person" if is_person else "organization"

    payload = {}
    for val, identity in zip(form_values, form_ids):
        inst = identity['instance']
        if inst == active_modal_entity_id or inst.startswith(f"{active_modal_entity_id}_row_"):
            c_type = identity['complex-type']
            field = identity['field']
            payload.setdefault(c_type, {})[field] = val

    root = read_existing(TEMP_XML_FILE)

    # 🔄 FIX A: Enforce full explicit OCADS namespace prefixes on master collection containers
    collection_node = root.find(f".//{{{NS_URL}}}{collection_name}") or root.find(f".//{collection_name}")
    if collection_node is None:
        collection_node = ET.SubElement(root, f"{{{NS_URL}}}{collection_name}")

    new_record = ET.SubElement(collection_node, f"{{{NS_URL}}}{element_tag}", {"object_id": active_modal_entity_id})

    # 🔄 FIX B: Deterministically resolve the grid summary string using the primary identity component blocks
    grid_summary_label = f"New {element_tag.title()} (#{active_modal_entity_id})"
    if is_person:
        name_block = payload.get('person_name', {})
        if name_block:
            grid_summary_label = f"{name_block.get('first', '')} {name_block.get('last', '')}".strip()
    else:
        org_block = payload.get('organization_definition', {})
        if org_block and org_block.get('name'):
            grid_summary_label = str(org_block.get('name'))

    tag_mapping = {
        'person_name': 'name',
        'contact_info': 'contact_info',
        'organization_pid': 'identifier',
        'person_pid': 'identifier',
        'uri_reference': 'link',
        'vocabulary_item_reference': 'country',
        'typed_identifier': 'identifier'
    }

    for c_type, fields in payload.items():
        if c_type == 'organization_ref':
            org_id_val = fields.get('object_id')
            if org_id_val:
                ET.SubElement(new_record, f"{{{NS_URL}}}organization", {"object_id": org_id_val})
            continue

        sub_element_tag = tag_mapping.get(c_type, c_type)
        container_node = ET.SubElement(new_record, f"{{{NS_URL}}}{sub_element_tag}")

        for field_name, field_val in fields.items():
            child_node = ET.SubElement(container_node, f"{{{NS_URL}}}{field_name}")
            child_node.text = str(field_val) if field_val is not None else ""

    save_existing(TEMP_XML_FILE, root)

    updated_rows = [{"object_id": active_modal_entity_id, "name": grid_summary_label}]
    return updated_rows


if __name__ == '__main__':
    app.run(debug=True,  dev_tools_hot_reload=False)