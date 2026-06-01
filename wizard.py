import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Output, Input, State, callback, ctx, ALL, MATCH, no_update
import xml.etree.ElementTree as ET
import uuid

import ocads_unified_components
from ocads_unified_components import *
from metadata_ref_selector import MetadataRefSelector
from metadata_list_group import MetadataListGroup
from variable_manager import PolymorphicVariableManager
from ocads_submit import MetadataSubmitButton
from utils import read_existing, save_existing, get_form_data_from_xml, NS_URL, TEMP_XML_FILE

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

# ===================================================================
# 🗺️ EXPERT CONFIG: MASTER WIZARD CHAPTER REGISTRY
# ===================================================================
WIZARD_REGISTRY = {
    "step-1": {
        "title": "Document & Archive Control",
        "desc": "Establish administrative metadata file definitions.",
        "elements": [
            # 🎯 THE FIX: Explicitly map the exact XSD type target name string
            {"type": "form", "class": "DocumentMetadata", "xsd_type": "document_metadata", "instance": "doc_root"}
        ]
    },
    "step-2": {
        "title": "Dataset Citation Profile",
        "desc": "Define primary dataset descriptions and licensing rules.",
        "elements": [
            {"type": "form", "class": "DatasetBaseFields", "xsd_type": "dataset_base_fields", "instance": "dataset_core"}
        ]
    },
    "step-3": {
        "title": "Tracking Identifiers",
        "desc": "Log operational EXPOCODES and cruise track designations.",
        "elements": [
            {"type": "form", "class": "ObservationIdentifiers", "xsd_type": "observation_identifiers", "instance": "dataset_core"}
        ]
    },
    "step-4": {
        "title": "Spatial & Temporal Coverage",
        "desc": "Lock in boundaries and recording date durations.",
        "elements": [
            {"type": "form", "class": "DataCoverageExtents", "xsd_type": "data_coverage_extents", "instance": "spatial_temporal_core"}
        ]
    },
    "step-5": {
        "title": "Polymorphic Variable Matrix",
        "desc": "Incorporate, isolate, and configure dataset variables, measurement instrumentation profiles, and sensor calculations.",
        "elements": [
            {"type": "custom", "component": PolymorphicVariableManager(instance_id="cruise_variables")}
        ]
    }
}

# (UI Style configurations remain exactly the same as your input file)
SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "20rem", "padding": "2rem 1rem",
    "background-color": "#f8f9fa", "border-right": "1px solid #dee2e6",
    "z-index": 1000, "overflowY": "auto"
}
CONTENT_STYLE = { "margin-left": "22rem", "padding": "2rem 2rem" }

nav_links = []
for step_key, meta in WIZARD_REGISTRY.items():
    step_num = step_key.split("-")[-1]
    nav_links.append(dbc.NavLink(f"⏱️ Step {step_num}: {meta['title']}", href=f"/{step_key}", active="exact", className="mb-2 rounded text-dark fw-semibold"))

sidebar_navigation = html.Div([
    html.H4("OCADS XML Factory", className="display-6 text-primary fw-bold mb-1"),
    html.Small("Schema Version 4.6 Driven", className="text-muted mb-4 d-block"),
    html.Hr(),
    dbc.Nav(nav_links, vertical=True, pills=True, className="mt-3"),
], style=SIDEBAR_STYLE)

app.layout = dbc.Container([
    dcc.Location(id="url", refresh=False),
    sidebar_navigation,
    html.Div(id="wizard-page-content", style=CONTENT_STYLE)
], fluid=True)


@callback(
    Output("wizard-page-content", "children"),
    Input("url", "pathname")
)
def render_wizard_step_layout(pathname):
    # 🎯 THE DASHBOARD INTERCEPT
    if pathname in ["/", None]:
        return html.Div([
            html.H1("🌊 OCADS XML Metadata Factory", className="display-4 text-primary fw-bold mb-2"),
            html.P("Welcome to the Schema Version 4.6 compliance management platform.", className="lead text-muted mb-4"),
            html.Hr(),

            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("🆕 Start Fresh", className="mb-0")),
                        dbc.CardBody([
                            html.P("Initialize a completely blank OCADS metadata document template context.", className="small card-text text-muted"),
                            dbc.Button("Begin Data Entry ➡️", href="/step-1", color="primary", size="sm")
                        ])
                    ], color="primary", outline=True, className="h-100 shadow-sm")
                ], width=6),

                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("📂 Start from Existing File", className="mb-0")),
                        dbc.CardBody([
                            html.P("Drag and drop an existing OCADS metadata file (.xml) here to automatically fill out all wizard steps.", className="small card-text text-muted"),
                            dcc.Upload(
                                id='upload-legacy-xml',
                                children=html.Div(['Drag and Drop or ', html.A('Select File')]),
                                style={
                                    'width': '100%', 'height': '40px', 'lineHeight': '40px',
                                    'borderWidth': '1px', 'borderStyle': 'dashed',
                                    'borderRadius': '5px', 'textAlign': 'center', 'fontSize': '12px'
                                }
                            )
                        ])
                    ], color="secondary", outline=True, className="h-100 shadow-sm")
                ], width=6),
            ], className="mb-4 mt-2"),

            html.Div([
                html.H5("📋 Key Operation Protocols", className="fw-bold mt-4 text-dark"),
                html.Ul([
                    html.Li("Progress is saved dynamically to the system file cache.", className="text-muted mb-1"),
                    html.Li("Ensure you explicitly save complex sections before altering the sidebar tabs.", className="text-muted mb-1"),
                    html.Li("Relational entries (People & Organizations) must be registered into global registry pools prior to assignment.", className="text-muted")
                ], className="small ps-3")
            ], className="p-3 border rounded bg-light")
        ], className="p-4")

    step_key = pathname.strip("/") if pathname not in ["/", None] else "step-1"
    if step_key not in WIZARD_REGISTRY:
        return html.Div([html.H1("404: Step Not Found", className="text-danger")])

    config = WIZARD_REGISTRY[step_key]
    layout_tree = [
        html.H2(config['title'], className="mb-1 text-dark fw-bold"),
        html.P(config['desc'], className="text-muted mb-4 fst-italic"),
        html.Hr(className="mb-4")
    ]

    submit_targets = []
    active_instance_id = "default"

    for el in config['elements']:
        if 'instance' in el:
            active_instance_id = el['instance']

        if el['type'] == 'form':
            # 🎯 THE FIX: Append the exact verified XSD type token target string to the submission list
            submit_targets.append(el['xsd_type'])
            existing_form_values = get_form_data_from_xml(TEMP_XML_FILE, el['xsd_type'])
            class_constructor = getattr(ocads_unified_components, el['class'])
            layout_tree.append(
                class_constructor(
                    instance_id=el['instance'],
                    initial_values=existing_form_values,
                    className="mb-4"
                )
            )

        elif el['type'] == 'custom':
            layout_tree.append(el['component'])

    if submit_targets:
        layout_tree.append(
            MetadataSubmitButton(
                instance_id=active_instance_id,
                targets=submit_targets,
                label=f"Save {config['title']} Specifications",
                color="success",
                className="w-100 p-2 mt-3 shadow-sm fw-bold"
            )
        )
    return layout_tree


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
            # 🎯 THE FIX: Detect relational reference selection elements matching the suffix rule
            if "__ref" in field_name:
                real_element_tag = field_name.split("__ref")[0]
                child_node = parent_node.find(f"{{{NS_URL}}}{real_element_tag}")
                if child_node is None:
                    child_node = ET.SubElement(parent_node, f"{{{NS_URL}}}{real_element_tag}")

                if field_value:
                    # Apply the structural identification pointer XML attribute cleanly
                    child_node.set("object_id", str(field_value))
                    child_node.text = ""  # Enforce structural child element cleanliness
            else:
                # Handle ordinary sequential text primitives safely
                child_node = parent_node.find(f"{{{NS_URL}}}{field_name}")
                if child_node is None:
                    child_node = ET.SubElement(parent_node, f"{{{NS_URL}}}{field_name}")
                child_node.text = str(field_value) if field_value is not None else ""

    save_existing(TEMP_XML_FILE, root)
    return [dash.no_update] * len(n_clicks_list)


@callback(
    Output({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    Input({'type': 'ref-grid', 'field_name': ALL, 'instance': ALL}, 'selectedRows'),
    State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'id'),
    prevent_initial_call=True
)
def bind_grid_selection_to_input(selected_rows_list, input_ids):
    if not ctx.triggered or ctx.triggered[0]['value'] is None:
        return [no_update] * len(input_ids)

    triggered_grid = ctx.triggered_id
    grid_index = None
    for idx, input_item in enumerate(ctx.inputs_list[0]):
        if input_item['id'] == triggered_grid:
            grid_index = idx
            break

    if grid_index is None:
        return [no_update] * len(input_ids)

    selected = selected_rows_list[grid_index]
    chosen_id = selected[0]['object_id'] if selected else ""

    outputs = []
    for identity in input_ids:
        # 🎯 THE FIX: Track and pair active grid changes directly back to the suffix-coded fields
        if (identity['instance'] == triggered_grid['instance'] and
                identity['field'] == f"{triggered_grid['field_name']}__ref"):
            outputs.append(chosen_id)
        else:
            outputs.append(no_update)
    return outputs

# (The remaining popup modal and polymorphic variable callback blocks stay intact)
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
        container = html.Div([form_child, dcc.Store(id={'type': 'active-modal-entity-id', 'field_name': field_name, 'instance': parent_instance}, data=new_entity_id)])
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
    if not save_clicks or not active_modal_entity_id: return dash.no_update
    field_name = ctx.triggered_id['field_name']
    is_person = "contact" in field_name or "submitter" in field_name or "author" in field_name
    collection_name = "people" if is_person else "organizations"
    element_tag = "person" if is_person else "organization"
    payload = {}
    for val, identity in zip(form_values, form_ids):
        inst = identity['instance']
        if inst == active_modal_entity_id or inst.startswith(f"{active_modal_entity_id}_row_"):
            payload.setdefault(identity['complex-type'], {})[identity['field']] = val
    root = read_existing(TEMP_XML_FILE)
    collection_node = root.find(f".//{{{NS_URL}}}{collection_name}") or root.find(f".//{collection_name}")
    if collection_node is None: collection_node = ET.SubElement(root, f"{{{NS_URL}}}{collection_name}")
    new_record = ET.SubElement(collection_node, f"{{{NS_URL}}}{element_tag}", {"object_id": active_modal_entity_id})
    tag_mapping = {'person_name': 'name', 'contact_info': 'contact_info', 'organization_pid': 'identifier', 'person_pid': 'identifier', 'uri_reference': 'link', 'vocabulary_item_reference': 'country', 'typed_identifier': 'identifier'}
    for c_type, fields in payload.items():
        if c_type == 'organization_ref':
            org_id_val = fields.get('object_id')
            if org_id_val: ET.SubElement(new_record, f"{{{NS_URL}}}organization", {"object_id": org_id_val})
            continue
        sub_element_tag = tag_mapping.get(c_type, c_type)
        container_node = ET.SubElement(new_record, f"{{{NS_URL}}}{sub_element_tag}")
        for f_name, f_val in fields.items():
            child_node = ET.SubElement(container_node, f"{{{NS_URL}}}{f_name}")
            child_node.text = str(f_val) if f_val is not None else ""
    save_existing(TEMP_XML_FILE, root)
    from utils import get_all_entities_from_xml
    return get_all_entities_from_xml(TEMP_XML_FILE, collection_name)

@callback(Output({'type': 'var-matrix-modal', 'instance': MATCH}, 'is_open'), Input({'type': 'open-var-modal-btn', 'instance': MATCH}, 'n_clicks'), Input({'type': 'close-var-modal-btn', 'instance': MATCH}, 'n_clicks'), Input({'type': 'save-var-matrix-btn', 'instance': MATCH}, 'n_clicks'), State({'type': 'var-matrix-modal', 'instance': MATCH}, 'is_open'), prevent_initial_call=True)
def toggle_variable_matrix_modal(o, c, s, is_open):
    if not ctx.triggered or ctx.triggered[0]['value'] in [0, None]: return no_update
    return not is_open

@callback(Output({'type': 'var-dynamic-form-container', 'instance': MATCH}, 'children'), Input({'type': 'var-factory-dropdown', 'instance': MATCH}, 'value'), prevent_initial_call=True)
def inject_polymorphic_variable_subform(selected_class_string):
    if not selected_class_string: return html.Div("Select a type profile above.", className="text-muted p-3 text-center small")
    new_var_row_id = f"VAR_{uuid.uuid4().hex[:8].upper()}"
    class_constructor = getattr(ocads_unified_components, selected_class_string)
    return html.Div([class_constructor(instance_id=new_var_row_id), dcc.Store(id={'type': 'active-var-spawned-class', 'instance': ctx.triggered_id['instance']}, data={"class_string": selected_class_string, "row_id": new_var_row_id})])

@callback(Output({'type': 'var-matrix-grid', 'instance': MATCH}, 'rowData'), Input({'type': 'save-var-matrix-btn', 'instance': MATCH}, 'n_clicks'), State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'value'), State({'type': 'primitive-input', 'complex-type': ALL, 'field': ALL, 'instance': ALL}, 'id'), State({'type': 'active-var-spawned-class', 'instance': MATCH}, 'data'), prevent_initial_call=True)
def commit_polymorphic_variable_to_xml(save_clicks, form_values, form_ids, active_spawn_meta):
    if not save_clicks or not active_spawn_meta: return dash.no_update
    target_row_id = active_spawn_meta['row_id']
    class_name = active_spawn_meta['class_string']
    class_to_xsd_tag_map = {'BasicVariable': 'basic', '劇StdObservedVariable': 'observed', 'DicMeasured': 'DIC', 'TaMeasured': 'TA', 'PhMeasured': 'pH', 'Co2ContinuousVariable': 'co2_continuous', 'Co2DiscreteVariable': 'co2_discrete'}
    xsd_element_tag = class_to_xsd_tag_map.get(class_name, 'basic')
    payload = {}
    for val, identity in zip(form_values, form_ids):
        if identity['instance'] == target_row_id:
            payload.setdefault(identity['complex-type'], {})[identity['field']] = val
    root = read_existing(TEMP_XML_FILE)
    variables_container = root.find(f".//{{{NS_URL}}}variables") or root.find(".//variables")
    if variables_container is None:
        collections_node = root.find(f".//{{{NS_URL}}}dataset_collections") or root.find(".//dataset_collections")
        if collections_node is None: collections_node = ET.SubElement(root, f"{{{NS_URL}}}dataset_collections")
        variables_container = ET.SubElement(collections_node, f"{{{NS_URL}}}variables")
    new_var_record = ET.SubElement(variables_container, f"{{{NS_URL}}}{xsd_element_tag}", {"object_id": target_row_id})
    for c_type, fields in payload.items():
        if c_type == class_name:
            for field_name, field_val in fields.items():
                ET.SubElement(new_var_record, f"{{{NS_URL}}}{field_name}").text = str(field_val) if field_val is not None else ""
        else:
            container_node = ET.SubElement(new_var_record, f"{{{NS_URL}}}{c_type}")
            for field_name, field_val in fields.items():
                ET.SubElement(container_node, f"{{{NS_URL}}}{field_name}").text = str(field_val) if field_val is not None else ""
    save_existing(TEMP_XML_FILE, root)
    from utils import get_variables_from_xml
    return get_variables_from_xml(TEMP_XML_FILE)


if __name__ == '__main__':
    app.run(debug=True, dev_tools_hot_reload=False)