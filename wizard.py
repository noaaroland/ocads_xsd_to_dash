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
from utils import (
    read_existing,
    save_existing,
    get_form_data_from_xml,
    NS_URL,
    TEMP_XML_FILE,
    get_variables_from_xml,
    get_all_entities_from_xml
)


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

# ===================================================================
# 🗺️ EXPERT CONFIG: MASTER WIZARD CHAPTER REGISTRY (CHUNKED)
# ===================================================================
WIZARD_REGISTRY = {
    "step-1": {
        "title": "Document & Archive Control",
        "desc": "Establish administrative metadata file definitions.",
        "elements": [
            {"type": "form", "class": "DocumentMetadata", "xsd_type": "document_metadata", "instance": "doc_root"}
        ]
    },

    # 🎯 STEP 2a: Core Primitives Only (All Personnel Fields Hidden)
    "step-2a": {
        "title": "Citation General Information",
        "desc": "Define primary dataset titles, abstract summaries, and publication timelines.",
        "elements": [
            {
                "type": "form",
                "class": "DatasetBaseFields",
                "xsd_type": "dataset_base_fields",
                "instance": "dataset_core",
                "exclude_fields": ["data_submitter", "principal_investigator", "dataset_contact", "author"]
            }
        ]
    },

    # 🎯 STEP 2b: Isolated Data Submitter Assignment
    "step-2b": {
        "title": "Citation - Data Submitter",
        "desc": "Assign the primary individual responsible for interacting with NCEI regarding this data submission.",
        "elements": [
            {
                "type": "direct_component",
                "component": lambda inst: MetadataRefSelector(
                    ref_field_name="data_submitter",
                    target_class="PersonDefinition",
                    parent_complex_type="dataset_metadata/dataset_base_fields",
                    instance_id=inst
                ),
                "instance": "dataset_core",
                "xpath_target": "dataset_metadata/dataset_base_fields"
            }
        ]
    },

    # 🎯 STEP 2c: Isolated Lead Principal Investigator Assignment
    "step-2c": {
        "title": "Citation - Principal Investigator",
        "desc": "Identify the lead cruise scientist monitoring the primary collection analytics.",
        "elements": [
            {
                "type": "direct_component",
                "component": lambda inst: MetadataRefSelector(
                    ref_field_name="principal_investigator",
                    target_class="PersonDefinition",
                    parent_complex_type="dataset_metadata/dataset_base_fields",
                    instance_id=inst
                ),
                "instance": "dataset_core",
                "xpath_target": "dataset_metadata/dataset_base_fields"
            }
        ]
    },

    # 🎯 STEP 2d: Isolated Public Dataset Contact Assignment
    "step-2d": {
        "title": "Citation - Dataset Contact",
        "desc": "Provide the global point of contact for external/public inquiries regarding dataset items.",
        "elements": [
            {
                "type": "direct_component",
                "component": lambda inst: MetadataRefSelector(
                    ref_field_name="dataset_contact",
                    target_class="PersonDefinition",
                    parent_complex_type="dataset_metadata/dataset_base_fields",
                    instance_id=inst
                ),
                "instance": "dataset_core",
                "xpath_target": "dataset_metadata/dataset_base_fields"
            }
        ]
    },

    # 🎯 STEP 2e: Isolated Structural Cited Authors Pool
    "step-2e": {
        "title": "Citation - Cited Authors",
        "desc": "Manage the list of primary literature and data citation authors associated with this cruise profile.",
        "elements": [
            {
                "type": "direct_component",
                "component": lambda inst: MetadataListGroup(
                    list_field_name="author",
                    component_class=ocads_unified_components.PersonDefinition,
                    instance_id=inst,
                    xpath_prefix="dataset_metadata/dataset_base_fields/cited_authors"
                ),
                "instance": "dataset_core",
                "xpath_target": "dataset_metadata/dataset_base_fields"
            }
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
            absolute_target_xpath = f"dataset_metadata/{el['xsd_type']}"
            submit_targets.append(absolute_target_xpath)

            from utils import get_form_data_from_xml
            existing_form_values = get_form_data_from_xml(TEMP_XML_FILE, absolute_target_xpath)

            class_constructor = getattr(ocads_unified_components, el['class'])

            # 🎯 THE REFACTOR: Pass the exclusion list straight into the constructor definition
            layout_tree.append(
                class_constructor(
                    instance_id=el['instance'],
                    initial_values=existing_form_values,
                    xpath_prefix=absolute_target_xpath,
                    exclude_fields=el.get('exclude_fields', []),  # Passed cleanly to the component
                    className="mb-4"
                )
            )
        elif el['type'] == 'direct_component':
            # 🎯 THE NEW BRANCH: Mount individual sub-components directly to the page grid
            submit_targets.append(el['xpath_target'])
            # Execute the lambda layout constructor passing the active shared instance tracking id
            layout_tree.append(el['component'](el['instance']))
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
    # 🎯 THE STATE: Ensure this matches your upgraded XPath configuration keys
    State({'type': 'primitive-input', 'xpath': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    State({'type': 'primitive-input', 'xpath': ALL, 'field': ALL, 'instance': ALL}, 'id'),
    prevent_initial_call=True
)
def handle_form_submission(n_clicks_list, form_values, form_ids):
    """
    Global form processing hub. Sweeps up regular input primitives and relational
    selectors using a sequential XPath tree-walker to maintain perfect structural depth.
    """
    # 🎯 THE FIX: Define the list wrapper immediately so it is always available
    default_return = [no_update] * len(n_clicks_list)

    if not ctx.triggered or ctx.triggered[0]['value'] in (0, None):
        return default_return

    try:
        triggered_id = ctx.triggered_id
        active_instance = triggered_id['instance']
        active_targets = triggered_id['targets'].split(',')

        root = read_existing(TEMP_XML_FILE)
        any_updates_performed = False
        root_tag_clean = root.tag.split('}')[-1]

        # Evaluate every input element currently rendered across the DOM tree
        for value, identity in zip(form_values, form_ids):
            # 1. Enforce Instance Isolation
            if identity['instance'] != active_instance:
                continue

            xpath_path_string = identity['xpath']
            field_name = identity['field']

            # 2. Scope Containment Check
            if not any(xpath_path_string.startswith(target) for target in active_targets):
                continue

            any_updates_performed = True

            # 3. 🗺️ THE TREE WALKER: Step down the absolute path layer-by-layer
            current_node = root
            path_steps = [step for step in xpath_path_string.split('/') if step]

            for idx, step in enumerate(path_steps):
                if idx == 0 and step == root_tag_clean:
                    continue

                found_node = current_node.find(f"./{{{NS_URL}}}{step}")
                if found_node is None:
                    found_node = ET.SubElement(current_node, f"{{{NS_URL}}}{step}")
                current_node = found_node

            # Apply the master context ID string to the core structural parent node container
            if any(xpath_path_string == target for target in active_targets):
                current_node.set("object_id", active_instance)

            # 4. Leaf Node Content Modification Block
            if "__ref" in field_name:
                real_element_tag = field_name.split("__ref")[0]
                child_node = current_node.find(f"./{{{NS_URL}}}{real_element_tag}")
                if child_node is None:
                    child_node = ET.SubElement(current_node, f"{{{NS_URL}}}{real_element_tag}")

                if value:
                    child_node.set("object_id", str(value))
                    child_node.text = ""
                else:
                    if "object_id" in child_node.attrib:
                        del child_node.attrib["object_id"]
            else:
                child_node = current_node.find(f"./{{{NS_URL}}}{field_name}")
                if child_node is None:
                    child_node = ET.SubElement(current_node, f"{{{NS_URL}}}{field_name}")
                child_node.text = str(value) if value is not None else ""

        # Commit state cleanly out to disk if updates occurred
        if any_updates_performed:
            save_existing(TEMP_XML_FILE, root)

    except Exception as e:
        print(f"⚠️ Internal Error inside handle_form_submission: {e}")

    # 🎯 THE FIX: Placed at the absolute base level of the function scope.
    # Guarantees that a valid list is ALWAYS returned, completely eliminating the None error.
    return default_return


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
        # 🎯 THE FIX: Track grid updates straight back to your suffix-coded fields
        if (identity['instance'] == triggered_grid['instance'] and
                identity['field'] == f"{triggered_grid['field_name']}__ref"):
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

        # 🎯 THE FIX: Provide explicit, standalone base paths for modal entity inputs
        if "contact" in field_name or "submitter" in field_name or "author" in field_name:
            form_child = PersonDefinition(instance_id=new_entity_id, xpath_prefix='person_definition')
        else:
            form_child = OrganizationDefinition(instance_id=new_entity_id, xpath_prefix='organization_definition')

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
    State({'type': 'primitive-input', 'xpath': ALL, 'field': ALL, 'instance': ALL}, 'value'),
    State({'type': 'primitive-input', 'xpath': ALL, 'field': ALL, 'instance': ALL}, 'id'),
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
            xpath_path = identity['xpath']
            field = identity['field']
            payload.setdefault(xpath_path, {})[field] = val

    root = read_existing(TEMP_XML_FILE)

    # 🎯 THE ROOT FIX: Scan namespace-agnostically to capture the pre-existing empty element tag
    collection_node = None
    for node in root.iter():
        if node.tag.split('}')[-1] == collection_name:
            collection_node = node
            break

    # Fall back to creating it only if it is genuinely missing from the file
    if collection_node is None:
        collection_node = ET.SubElement(root, f"{{{NS_URL}}}{collection_name}")

    # Append the new entity directly inside the retrieved collection container node
    new_record = ET.SubElement(collection_node, f"{{{NS_URL}}}{element_tag}", {"object_id": active_modal_entity_id})

    for xpath_path, fields in payload.items():
        if xpath_path == 'organization_ref':
            org_id_val = fields.get('object_id')
            if org_id_val:
                ET.SubElement(new_record, f"{{{NS_URL}}}organization", {"object_id": org_id_val})
            continue

        if xpath_path in ['person_definition', 'organization_definition']:
            target_container = new_record
        else:
            sub_element_tag = xpath_path.split('/')[-1]
            target_container = ET.SubElement(new_record, f"{{{NS_URL}}}{sub_element_tag}")

        for f_name, f_val in fields.items():
            child_node = ET.SubElement(target_container, f"{{{NS_URL}}}{f_name}")
            child_node.text = str(f_val) if f_val is not None else ""

    save_existing(TEMP_XML_FILE, root)
    return get_all_entities_from_xml(TEMP_XML_FILE, collection_name, root_node=root)


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
    return get_variables_from_xml(TEMP_XML_FILE)


if __name__ == '__main__':
    app.run(debug=True, dev_tools_hot_reload=False)