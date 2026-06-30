This project was build using Python 3.12. In the virtual environment,
associated with the project I installed the following packages:
- dash
- dash-bootstrap-components
- dash-ag-grid
- flask

See the requirements.txt file for more details.

You can install packages in Intellij IDEA from File -> Project Structure -> Platform Settings -> Packages -> + button -> Search for package -> Install package

## Getting Started

To begin run the generate_unified_library.py which will create the component library in the file ocads_unified_components.py
Run app.py or wizard.py to see the demos of the components.

## Project Files

### Core Entry Points

**generate_unified_library.py**
> This creates the component library from the ocads_metadata_schema.xsd file. You have to run this file first.

**app.py**
> This is a demo app that uses a few of the components from the generated library.

**wizard.py**
> This is a more elaborate app that uses the component library to create a wizard style app.

### Component System

**ocads_unified_components.py**
> Output from the component library generation. DO NOT EDIT. We want to fix the generator if there are fixed needed.

**metadata_ref_selector.py**
> This is a component that wraps things like PersonDefintion, and OrganizationDefinition which allows the user to
> people and organizations to be selected. These items are saved in a repository of like items and the reference is
> saved in the place where the instance is used.

**metadata_list_group.py**
> This a component that wraps things that are accumulated into lists in place.

**variable_manager.py**
> A first attemp at a component that manages the variable hierarchy

**ocads_submit.py**
> A generic submit button that can be used for any form.

### Utilities & Schema

**utils.py**
> Various utility functions to read the XML and write back changes.

**xsd_combine.py**
> I used this to combine the schema files into a single XSD file.
