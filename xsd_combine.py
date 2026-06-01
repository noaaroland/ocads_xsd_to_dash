import os
from lxml import etree

def flatten_xsd(main_xsd_path, output_xsd_path):
    """
    Reads a main XSD file, recursively resolves and merges all <xs:include>
    schemas into a single, complete XSD schema file.
    """
    # Use an XML parser that removes blank text to ensure clean pretty-printing later
    parser = etree.XMLParser(remove_blank_text=True, load_dtd=True, resolve_entities=True, no_network=False)

    # Define the absolute path to your XSD file
    xsd_path = r"C:\Users\schweitzer\Documents\IntellijProjects\xsd_to_dash\schema\archival.xsd"

    # Extract the exact folder location (C:\Users\...\schema)
    schema_folder = os.path.dirname(os.path.abspath(main_xsd_path))

    # Parse the root master schema
    main_tree = etree.parse(main_xsd_path, parser, base_url=schema_folder)
    main_root = main_tree.getroot()

    # Standard XML Schema namespace mapping for XPath queries
    ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}

    # Track visited files to prevent infinite loops and duplicate inclusions
    visited_files = {os.path.abspath(main_xsd_path)}

    def resolve_includes(current_root, current_path):
        base_dir = os.path.dirname(current_path)

        # Find all direct <xs:include> children of the current schema root
        includes = current_root.xpath('./xs:include', namespaces=ns)

        for include in includes:
            location = include.get('schemaLocation')
            if not location:
                include.getparent().remove(include)
                continue

            # Resolve the absolute path of the included XSD relative to its parent file
            include_path = os.path.abspath(os.path.join(base_dir, location))

            # If already processed, just strip the include tag and move on
            if include_path in visited_files:
                include.getparent().remove(include)
                continue

            if os.path.exists(include_path):
                visited_files.add(include_path)

                # Parse the sub-schema
                inc_tree = etree.parse(include_path, parser)
                inc_root = inc_tree.getroot()

                # Deeply resolve any nested includes inside this sub-schema first
                resolve_includes(inc_root, include_path)

                # Insert the sub-schema elements exactly where the <xs:include> tag was
                parent = include.getparent()
                index = parent.index(include)

                # Reversing ensures they stay in their original relative sequence when inserted
                for child in reversed(inc_root.getchildren()):
                    parent.insert(index, child)
            else:
                print(f"Warning: Could not find file {include_path}")

            # Remove the now-processed <xs:include> tag
            include.getparent().remove(include)

    # Start the recursive flattening process
    resolve_includes(main_root, main_xsd_path)

    # Save the consolidated schema to a new file
    with open(output_xsd_path, 'wb') as f:
        f.write(etree.tostring(
            main_tree,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        ))
    print(f"Successfully combined XSDs into: {output_xsd_path}")

if __name__ == "__main__":
    main_xsd_path = "schema/dataset_metadata.xsd"
    output_xsd_path = "full_schema.xsd"
    flatten_xsd(main_xsd_path, output_xsd_path)
