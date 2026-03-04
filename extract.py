import json

with open('/home/belal/.gemini/antigravity/brain/6128f82e-4149-4d34-b67e-c66a9e06e3d2/.system_generated/steps/50/output.txt', 'r', encoding='utf-8') as f:
    response_data = json.load(f)
    
if 'content' in response_data and isinstance(response_data['content'], list) and len(response_data['content']) > 0:
    html = response_data['content'][0]
else:
    html = str(response_data)

try:
    data_str = html.split('<script id="__NEXT_DATA__" type="application/json">')[1].split('</script>')[0]
    data = json.loads(data_str)
    
    with open('next_data.json', 'w', encoding='utf-8') as f_out:
        json.dump(data, f_out, indent=2)
    
    pageProps = data.get('props', {}).get('pageProps', {})
    
    with open('pageProps.json', 'w', encoding='utf-8') as f2:
        json.dump(pageProps, f2, indent=2)
        
    print("Extracted pageProps with keys:", pageProps.keys())
    
    if 'page' in pageProps:
        print("Keys in pageProps['page']:", pageProps['page'].keys())
        
        if 'components' in pageProps['page']:
            components = pageProps['page']['components']
            print(f"Found {len(components)} components.")
            for i, comp in enumerate(components):
                comp_type = comp.get('__typename', 'Unknown')
                print(f"Component {i}: {comp_type}")
                if comp_type == 'BlockIntegrationsFilteringModelRecord':
                    if 'categories' in comp:
                        print(f"  -> Found {len(comp['categories'])} categories")
                        
except IndexError:
    print("Could not find __NEXT_DATA__")
except json.JSONDecodeError as e:
    print("Failed to decode JSON:", e)
