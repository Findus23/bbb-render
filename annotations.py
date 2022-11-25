import collections
import operator
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

from intervaltree import IntervalTree, Interval

SlideInfo = collections.namedtuple('SlideInfo', ['id', 'width', 'height', 'start', 'end'])
tmpdir = Path("./tmp").absolute()
doc = ET.parse('tmp/shapes.svg')

kddoc = ET.parse('/home/lukas/tmp/test.kdenlive')
mlt = kddoc.getroot()
playlist = mlt.find("playlist")
track_plst = mlt.find("playlist[@id='playlist6']")
for child in list(track_plst):
    track_plst.remove(child)

timefactor = 30

width = 1920 * 2
height = 1080 * 2

current_time = 0
id = 1000

slides = {}
slide_time = IntervalTree()
for img in doc.iterfind('./{http://www.w3.org/2000/svg}image[@class="slide"]'):
    info = SlideInfo(
        id=img.get('id'),
        width=int(img.get('width')),
        height=int(img.get('height')),
        start=round(float(img.get('in')) * timefactor),
        end=round(float(img.get('out')) * timefactor),
    )
    slides[info.id] = info

for canvas in doc.iterfind('./{http://www.w3.org/2000/svg}g[@class="canvas"]'):

    info = slides[canvas.get('image')]
    t = IntervalTree()
    for index, shape in enumerate(canvas.iterfind('./{http://www.w3.org/2000/svg}g[@class="shape"]')):
        shape.set('style', shape.get('style').replace(
            'visibility:hidden;', ''))
        timestamp = round(float(shape.get('timestamp')) * timefactor)
        undo = round(float(shape.get('undo')) * timefactor)
        if undo < 0:
            undo = info.end

        # Clip timestamps to slide visibility
        start = min(max(timestamp, info.start), info.end)
        end = min(max(undo, info.start), info.end)

        if start == end:  # Null Interval objects not allowed in IntervalTree
            continue
        t.addi(start, end, [(index, shape)])

    t.split_overlaps()
    t.merge_overlaps(strict=True, data_reducer=operator.add)
    interval: Interval
    for index, interval in enumerate(sorted(t)):
        svg = ET.Element('{http://www.w3.org/2000/svg}svg')
        svg.set('version', '1.1')
        svg.set('width', f'{info.width}px')
        svg.set('height', f'{info.height}px')
        svg.set('viewBox', f'0 0 {info.width} {info.height}')

        # We want to discard all but the last version of each
        # shape ID, which requires two passes.
        shapes = sorted(interval.data)
        shape_index = {}
        for index, shape in shapes:
            shape_index[shape.get('shape')] = index
        for index, shape in shapes:
            if shape_index[shape.get('shape')] != index: continue
            svg.append(shape)

        path = tmpdir / f'annotations-{info.id}-{index}.svg'
        # with open(path, 'wb') as fp:
        #     fp.write(ET.tostring(svg, xml_declaration=True))
        #
        # run([
        #     "inkscape",
        #     "--export-type", "png",
        #     "--export-width",str(width),
        #     "--export-height",str(height),
        #     str(path)])
        path = path.with_suffix(".png")
        producer = ET.Element("producer")
        producer.set("id", f"producer{id}")
        properties = {
            "resource": str(path),
            "mlt_service": "qimage",
            "kdenlive:id": str(id)
        }
        for key, value in properties.items():
            prop = ET.Element("property")
            prop.set("name", key)
            prop.text = value
            producer.append(prop)
        id += 1
        mlt.insert(2, producer)
        pl_entry = ET.Element("entry")
        pl_entry.set("producer", producer.get("id"))
        playlist.append(pl_entry)
        blank_length = interval.begin - current_time
        if blank_length:
            blank = ET.Element("blank")
            blank.set("length", str(blank_length))
            track_plst.append(blank)

        entry = ET.Element("entry")
        entry.set("producer", producer.get("id"))
        entry.set("out", str(interval.length()))

        print(interval.begin)
        prop = ET.Element("property")
        prop.set("name", "kdenlive:id")
        prop.text = str(id)
        entry.append(prop)
        track_plst.append(entry)
        current_time = interval.end

        # asset = self._get_asset(path)
        # width, height = self._constrain(
        #     (info.width, info.height),
        #     (self.slides_width, self.opts.height))
        # self._add_clip(layer, asset, interval.begin, 0, interval.end - interval.begin,
        #                0, 0, width, height)

kddoc.write("out.kdenlive")
