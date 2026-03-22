import os
import zipfile
import uuid
import datetime
from pathlib import Path
from io import BytesIO

def generate_epub(title: str, author: str, chapters: list[dict], output_path: str = None) -> bytes:
    """Generate a standard EPUB file purely with zipfile."""
    epub = BytesIO()
    
    with zipfile.ZipFile(epub, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first, uncompressed
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        
        # META-INF/container.xml
        container = '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        zf.writestr('META-INF/container.xml', container)
        
        # Generate items
        manifest_items = []
        spine_items = []
        nav_points = []
        
        author_xml = f"<dc:creator>{author}</dc:creator>" if author else ""
        book_id = str(uuid.uuid4())
        
        for i, ch in enumerate(chapters, start=1):
            ch_id = f"chapter_{i}"
            ch_title = ch.get("title", f"Chapter {i}")
            # Replace markdown newlines with HTML paragraphs
            text = ch.get("text", ch.get("raw_text", ""))
            html_text = "".join(f"<p>{p.strip()}</p>" for p in text.splitlines() if p.strip())
            
            html_content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>{ch_title}</title>
</head>
<body>
<h1>{ch_title}</h1>
{html_text}
</body>
</html>'''
            zf.writestr(f'OEBPS/{ch_id}.html', html_content)
            manifest_items.append(f'<item id="{ch_id}" href="{ch_id}.html" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')
            nav_points.append(f'''
    <navPoint id="navPoint-{i}" playOrder="{i}">
      <navLabel><text>{ch_title}</text></navLabel>
      <content src="{ch_id}.html"/>
    </navPoint>''')
            
        opf_content = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    {author_xml}
    <dc:language>zh-CN</dc:language>
    <dc:identifier id="BookId">urn:uuid:{book_id}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {"".join(manifest_items)}
  </manifest>
  <spine toc="ncx">
    {"".join(spine_items)}
  </spine>
</package>'''
        zf.writestr('OEBPS/content.opf', opf_content)
        
        ncx_content = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    {"".join(nav_points)}
  </navMap>
</ncx>'''
        zf.writestr('OEBPS/toc.ncx', ncx_content)
        
    epub.seek(0)
    data = epub.read()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(data)
    return data
