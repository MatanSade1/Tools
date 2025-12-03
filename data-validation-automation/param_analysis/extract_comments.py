import re

def extract_parameter_comments(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Split content by parameter sections (marked by ##)
    sections = content.split('## ')[1:]  # Skip the first empty part
    
    comments = {}
    for section in sections:
        # Get parameter name (first line)
        param_name = section.split('\n')[0].strip()
        
        # Find the comments section
        comment_section = re.search(r'\*\*Comments:\*\*\n```\n(.*?)\n```', section, re.DOTALL)
        if comment_section:
            # Extract actual comment (after #)
            comment_text = comment_section.group(1)
            actual_comment = ''
            for line in comment_text.split('\n'):
                if '#' in line:
                    actual_comment = line.split('#', 1)[1].strip()
                    if actual_comment and actual_comment != "Add your comments here:":  # Skip empty and template comments
                        comments[param_name] = actual_comment
                        break
    
    return comments

# Extract and print comments
comments = extract_parameter_comments('logs/parameter_analysis_comments.md')
for param, comment in sorted(comments.items()):
    print(f"{param}: {comment}") 