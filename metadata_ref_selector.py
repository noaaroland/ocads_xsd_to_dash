import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from utils import read_existing, save_existing, TEMP_XML_FILE, NS_URL, get_all_entities_from_xml

class MetadataRefSelector(html.Div):
    """
    A generic component used to configure and resolve schema references (Refs).
    Presents an AG Grid of existing records and a modal form to create a new instance.
    Automatically pre-selects and checks rows matching existing XML selections.
    """
    def __init__(self, ref_field_name, target_class, parent_complex_type, instance_id='default', className=None, **kwargs):
        super().__init__(**kwargs)

        self.ref_field_name = ref_field_name
        self.target_class = target_class.lower()
        self.instance_id = instance_id
        self.parent_complex_type = parent_complex_type

        self.comp_id_prefix = f"ref-{ref_field_name}-{instance_id}"
        grid_title = f"Select {target_class.replace('Definition','')} for '{ref_field_name.replace('_', ' ').title()}'"

        column_defs = [
            {'headerName': 'System Reference ID', 'field': 'object_id', 'width': 180, 'checkboxSelection': True},
            {'headerName': 'Selected Identity Descriptor', 'field': 'name', 'flex': 1}
        ]

        is_person = "person" in self.target_class
        target_collection = "people" if is_person else "organizations"

        try:
            initial_rows = get_all_entities_from_xml(TEMP_XML_FILE, target_collection)
        except Exception:
            initial_rows = []

        # 🎯 THE HYDRATION FIX: Look up if an existing selection lives in the XML scratchpad
        existing_id = ""
        selected_rows = []
        try:
            root = read_existing(TEMP_XML_FILE)
            # Find the parent block using namespace wildcards
            parent_node = root.find(f".//{{*}}{parent_complex_type}")
            if parent_node is not None:
                # Isolate the exact reference pointer element child
                ref_node = parent_node.find(f"./{{*}}{ref_field_name}")
                if ref_node is not None:
                    existing_id = ref_node.get("object_id", "")

            # If an active ID exists, locate the exact row dict matching that constraint
            if existing_id:
                selected_rows = [row for row in initial_rows if row['object_id'] == existing_id]
        except Exception:
            pass  # Fail gracefully if the file is empty or missing on primary init

        layout = [
            html.Div([
                html.Label(grid_title, className='fw-bold text-dark mb-2 d-inline-block'),
                # Hydrate the hidden input state seamlessly on page load
                dcc.Input(
                    id={'type': 'primitive-input', 'complex-type': parent_complex_type, 'field': f"{ref_field_name}__ref", 'instance': instance_id},
                    type='text',
                    value=existing_id,  # ✅ Seeded state
                    style={'display': 'none'}
                )
            ]),

            dag.AgGrid(
                id={'type': 'ref-grid', 'field_name': self.ref_field_name, 'instance': self.instance_id},
                columnDefs=column_defs,
                rowData=initial_rows,
                selectedRows=selected_rows,  # ✅ AG Grid will automatically check this row on mount!
                dashGridOptions={"rowSelection": "single", "popupParent": {"className": "root"}},
                className="ag-theme-alpine"
            ),

            dbc.Button(
                f"➕ Create New {target_class.replace('Definition','')}",
                id={'type': 'open-modal-btn', 'field_name': ref_field_name, 'instance': instance_id},
                color="secondary",
                size="sm",
                className="mt-2"
            ),

            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(f"Register New {target_class.replace('Definition','')} Definition")),
                dbc.ModalBody(id={'type': 'modal-body-form', 'field_name': ref_field_name, 'instance': instance_id}),
                dbc.ModalFooter([
                    dbc.Button("Cancel", id={'type': 'close-modal-btn', 'field_name': ref_field_name, 'instance': instance_id}, color="light"),
                    dbc.Button("Save Definition", id={'type': 'save-entity-btn', 'field_name': ref_field_name, 'instance': instance_id}, color="success")
                ])
            ], id={'type': 'ref-modal', 'field_name': ref_field_name, 'instance': instance_id}, is_open=False, size="lg")
        ]

        default_class = 'p-3 border rounded bg-white shadow-sm mb-4'
        self.className = f'{default_class} {className}' if className else default_class
        self.children = layout