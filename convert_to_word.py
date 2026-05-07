import markdown
from docx import Document
from htmldocx import HtmlToDocx
import sys

def convert_md_to_docx(md_path, docx_path):
    # Read Markdown
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    # Convert Markdown to HTML
    html_text = markdown.markdown(md_text, extensions=['extra'])
    
    # Pre-process HTML to add a basic wrapper (helps parser)
    html_text = "<html><head></head><body>" + html_text + "</body></html>"
    
    # Create Word Doc
    doc = Document()
    new_parser = HtmlToDocx()
    
    # Append HTML to Doc
    new_parser.add_html_to_document(html_text, doc)
    
    # Save
    doc.save(docx_path)
    print("Successfully saved docx file!")

if __name__ == '__main__':
    md_file = '/Users/yc/.gemini/antigravity/scratch/ProjectChronos/competition_report_detailed.md'
    docx_file = '/Users/yc/.gemini/antigravity/scratch/ProjectChronos/AI投資創意競賽報告書_詳細版.docx'
    convert_md_to_docx(md_file, docx_file)
