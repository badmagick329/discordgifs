from typing import Optional
import re
import os

def get_available_name(name: str, ext: Optional[str] = None) -> str:
    """
    Returns a file or folder name that is currently not in use.
    """
    if name == "":
        name = "temp"
    postfix_pat = re.compile(r".+\((\d+)\).*")
    if os.path.isfile(name) and ext:
        ext = ext.replace(".", "")
        name = f"{os.path.splitext(name)[0]}.{ext}"
    new_name = name
    while os.path.exists(new_name):
        match = re.search(postfix_pat, new_name)
        if match:
            new_num = int(match.groups()[-1]) + 1
            new_name = (
                new_name[: match.start(1)]
                + str(new_num)
                + new_name[match.end(1) :]
            )
        else:
            name, ext = os.path.splitext(new_name)
            new_name = name + "(0)" + ext
    return new_name
