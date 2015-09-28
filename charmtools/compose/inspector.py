# coding=utf-8
import json
from ruamel import yaml
from charmtools.compose import config
from charmtools import utils

theme = {
    0: "normal",
    1: "green",
    2: "cyan",
    3: "magenta",
    4: "yellow",
    5: "red",
}


def scan_for(col, cur, depth):
    for e, (rel, d) in col[cur:]:
        if d and d == depth:
            return True
    return False


def get_prefix(walk, cur, depth, next_depth):
    guide = []
    for i in range(depth):
        # scan forward in walk from i seeing if a subsequent
        # entry happens at each depth
        if scan_for(walk, cur, i):
            guide.append(" │  ")
        else:
            guide.append("    ")
    if depth == next_depth:
        prefix = " ├─── "
    else:
        prefix = " └─── "
    return "{}{}".format("".join(guide), prefix)


def inspect(charm, force_styling=False):
    tw = utils.TermWriter(force_styling=force_styling)
    manp = charm / ".composer.manifest"
    comp = charm / "composer.yaml"
    if not manp.exists() or not comp.exists():
        return
    manifest = json.loads(manp.text())
    composer = yaml.load(comp.open())
    a, c, d = utils.delta_signatures(manp)

    # ordered list of layers used for legend
    layers = list(manifest['layers'])

    def get_depth(e):
        rel = e.relpath(charm)
        depth = len(rel.splitall()) - 2
        return rel, depth

    def get_suffix(rel):
        suffix = ""
        if rel in a:
            suffix = "+"
        elif rel in c:
            suffix = "*"
        return suffix

    def get_color(rel):
        # name of layer this belongs to
        color = tw.term.normal
        if rel in manifest['signatures']:
            layer = manifest['signatures'][rel][0]
            layer_key = layers.index(layer)
            color = getattr(tw, theme.get(layer_key, "normal"))
        else:
            if entry.isdir():
                color = tw.blue
        return color

    tw.write("Inspect %s\n" % composer["is"])
    for layer in layers:
        tw.write("# {color}{layer}{t.normal}\n",
                 color=getattr(tw, theme.get(
                     layers.index(layer), "normal")),
                 layer=layer)
    tw.write("\n")
    tw.write("{t.blue}{target}{t.normal}\n", target=charm)

    ignorer = utils.ignore_matcher(config.DEFAULT_IGNORES)
    walk = sorted(utils.walk(charm, get_depth),
                    key=lambda x: x[1][0])
    for i in range(len(walk) - 1):
        entry, (rel, depth) = walk[i]
        nEnt, (nrel, ndepth) = walk[i + 1]
        if not ignorer(rel):
            continue

        tw.write("{prefix}{layerColor}{entry} "
                    "{t.bold}{suffix}{t.normal}\n",
                    prefix=get_prefix(walk, i, depth, ndepth),
                    layerColor=get_color(rel),
                    suffix=get_suffix(rel),
                    entry=rel.name)
