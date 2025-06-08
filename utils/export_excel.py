def add_all_border(cell_):
    """ Add thin border to all sides of the cell """
    cell_.border = Border(left=_BD, top=_BD, right=_BD, bottom=_BD)

def cell_center(cell_):
    """ Set cell alignment to center horizontally and vertically """
    cell_.alignment = _CENTER

def cell_right(cell_):
    """ Set cell alignment to right horizontally and center vertically """
    cell_.alignment = _RIGHT

def gen_workbook(title, thead, trs, trs_types=()):
    wb = Workbook()
    ws = wb.active
    ws.append([title, ])
    ws.append(thead)
    for tr in trs:
        _tr = []
        for index, value in enumerate(tr):
            try:
                value_type = trs_types[index]
            except IndexError:
                value_type = "str"
            if value_type == "str":
                value = str(value)
            elif value_type == "int":
                value = int(value)
            elif value_type == "float":
                value = float(value)
            else:
                raise ValueError("Unrecognized column data type: " + str(value_type))
            _tr.append(value)
        ws.append(_tr)
    # Merge first row (title)
    ws.merge_cells("A1:%s1" % ws[2][-1].column_letter)
    # Set all cells to center alignment and add border
    for cell in itertools.chain.from_iterable(ws.rows):
        cell_center(cell)
        add_all_border(cell)
    # Set font for each row
    ws['A1'].font = _FONT_TITLE
    for cell in ws[2]:
        cell.font = _FONT_HEADER
    for cell in itertools.chain.from_iterable(list(ws.rows)[2:]):
        cell.font = _FONT_VALUE
    # Adjust column width
    for col in ws.columns:
        max_len_set = set()
        for cell in col:
            cell_len = 0
            if not cell.value:
                continue
            for char in str(cell.value):
                if ord(char) <= 256:
                    cell_len += 1.3
                else:
                    cell_len += 2.6
            max_len_set.add(cell_len)
        ws.column_dimensions[col[1].column_letter].width = max(max_len_set)
    return save_virtual_workbook(wb)
