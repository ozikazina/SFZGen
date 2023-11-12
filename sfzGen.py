"""
MIT License

Copyright (c) 2023 Ondřej Vlček

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys, re, os, argparse, math, io
from collections import defaultdict
from yaml import load, dump
from yaml import CLoader as Loader, CDumper as Dumper

#	------------------------------------------------------------

#	------------------------------------------------------------

noteNames = {'c': 0, 'd': 2, 'e':4, 'f':5, 'g':7, 'a':9, 'b':11}
R_note = re.compile(r'^([abcdefg])([#b])?(-?\d+)$')
R_format = re.compile(r'\.(?:wav|ogg|flac)$')
R_dyn = re.compile(r'p+$|mp$|mf$|f+$|vl?\d+$|l\d+$')
R_num = re.compile(r'\d+$')
R_rr = re.compile(r'^rr(\d+)$')

class Sample(object):
	def __init__(self, name):
		self.name = name
		self.offset = 0
		self.vol = 0
		self.pan = 0

	def __str__(self):
		return "-> %d ^ %ddB <> %d :: %s" % (self.offset, self.vol, self.pan, self.name)

class Global(object):
	@classmethod
	def help(cls):
		print('''
--------------------------------------------------------------------
--------------------------------------------------------------------

Global settings:

	output - output file name without extension.
--------------------------------------------------------------------
	comment - dictionary of arbitrary values

	volume - added to layer volumes.
	attack - default 0.004
	release - default 0.3
	exponent - velocity exponent, applied to even distribution of transitions from 0-1 (0-127)
	min - minimum index. Notes outside range are ignored. No default.
	max - maximum index. No default.
	octaveOffset
	transpose
	middleC - index of middle C for indexed naming. Default 60.
	stride - index step. Default 1.

	crossfade - crossfade based on key.
	unpitched - don't vary pitch based on key.
	invertDynamics - invert order of dynamics.
	exact - won't extend note key ranges.
	skipAnalysis - don't analyze any soundwaves. Equal to --force.

	knobs - create Attack, Release and Release Volume controls, if present.

	sustain - layer element, see Layer settings.
	# or
	layers:	#dictionary of layers.
		a:
			...
		release:
			...

	# Editing - filter, sub, map - see Layer settings.''')

	def __init__(self, layer:dict):
		self.name = layer["name"] if "name" in layer else "Generated Instrument"
		self.volume = float(layer["volume"]) if "volume" in layer else 0.0

		self.attack = float(layer["attack"]) if "attack" in layer else 0.004
		self.release = float(layer["release"]) if "release" in layer else 0.3

		self.exponent = float(layer["exponent"]) if "exponent" in layer else 0.6

		self.min = int(layer["min"]) if "min" in layer else None
		self.max = int(layer["max"]) if "max" in layer else None

		self.map = {x.lower():y.lower() for (x,y) in layer["map"].items()} if "map" in layer else {}
		self.sub = layer["sub"] if "sub" in layer else []
		self.sub = [(re.compile(s["from"]), s["to"]) for s in self.sub]

		self.filter = re.compile(layer["filter"]) if "filter" in layer else None
		self.split = re.compile(layer["split"]) if "split" in layer else re.compile(" ")

		self.octaveOffset = int(layer["octave"]) if "octave" in layer else 0
		self.transpose = int(layer["transpose"]) if "transpose" in layer else 0

		self.indexOffset = int(layer["middleC"])-60 if "middleC" in layer else 0
		self.stride = int(layer["stride"]) if "stride" in layer else 1

		self.crossfade = "crossfade" in layer
		self.unpitched = "unpitched" in layer
		self.skipAnalysis = self.skipAnalysis = "skipAnalysis" in layer or "force" in layer
		self.invertDynamics = "invertDynamics" in layer

		self.knobs = False if args.noknobs else "knobs" in layer

		self.exact = "exact" in layer

class Layer(object):
	@classmethod
	def help(cls):
		print('''
--------------------------------------------------------------------
--------------------------------------------------------------------

Layer settings:

	source - path to source folder.
--------------------------------------------------------------------
	# Additive to global:
	volume
	octave
	transpose
	
	# Replacements:
	attack
	release
	min
	max
	middleC
	stride
	exponent
	
	# Overriden by global:
	crossfade
	unpitched
	invertDynamics
	exact
	skipAnalysis - don't analyze soundwaves for layer.
	
	isRelease - release layer. Can just be named "release" for same effect.
	alwaysRelease - triggered on note up regardless of sustain pedal.
	
	onekey - only one note on given layer. Doesn't need an identifiable index. Can have RRs.
	
	knob - create volume knob. Labeled based on layer name.
	knobPercent - default value of knob. 0-100 integer.
	
	- Editing in sequence (individually preceeded by global equivalents):
	filter - regex. Only matches (anywhere in filename) get processed further. Case sensitive.
	sub - list of from-to regexes. Applied to whole filename. Case sensitive.
	split - regex. Splits filename into chunks. Case sensitive.
	map - dictionary of key-replacement elements. Applied to split chunks of filenames. Case INsensitive.

--------------------------------------------------------------------''')

	def __init__(self, name:str, layer:dict):
		self.name = name
		self.attack = float(layer["attack"]) if "attack" in layer else 0
		self.release = float(layer["release"]) if "release" in layer else 0
		self.volume = float(layer["volume"]) if "volume" in layer else 0.0
		self.volume += globalLayer.volume
		self.exponent = float(layer["exponent"]) if "exponent" in layer else globalLayer.exponent

		self.min = int(layer["min"]) if "min" in layer else globalLayer.min
		self.max = int(layer["max"]) if "max" in layer else globalLayer.max

		self.map = {x.lower():y.lower() for (x,y) in layer["map"].items()} if "map" in layer else {}
		self.sub = layer["sub"] if "sub" in layer else []
		self.sub = [(re.compile(s["from"]), s["to"]) for s in self.sub]

		self.filter = re.compile(layer["filter"]) if "filter" in layer else None
		self.split = re.compile(layer["split"]) if "split" in layer else globalLayer.split

		self.octaveOffset = int(layer["octave"]) if "octave" in layer else 0
		self.octaveOffset += globalLayer.octaveOffset
		self.transpose = int(layer["transpose"]) if "transpose" in layer else 0
		self.transpose += globalLayer.transpose

		self.srcDir = layer["source"]

		self.indexOffset = int(layer["middleC"])-60 if "middleC" in layer else globalLayer.indexOffset
		self.stride = int(layer["stride"]) if "stride" in layer else globalLayer.stride

		self.crossfade = "crossfade" in layer or globalLayer.crossfade
		self.invertDynamics = "invertDynamics" in layer or globalLayer.invertDynamics

		self.unpitched = "unpitched" in layer or globalLayer.unpitched
		self.isRelease = "isRelease" in layer or name == "release"
		self.alwaysRelease = "alwaysRelease" in layer

		self.onekey = "onekey" in layer
		self.exact = "exact" in layer or globalLayer.exact

		self.knob = False if args.noknobs else "knob" in layer
		self.knobVal = int(layer["knobPercent"] * 127 / 100) if "knobPercent" in layer else 127

		self.skipAnalysis = "skipAnalysis" in layer or "force" in layer
		self.dynamics = defaultdict(lambda: defaultdict(dict))

#	------------------------------------------------------------

if "-hf" in sys.argv or "--helpFormat" in sys.argv:
	Global.help()
	Layer.help()
	sys.exit(0)

parser = argparse.ArgumentParser(description='Create SFZ instruments from samples.')
parser.add_argument('-x', '--stdout', dest="stdout", action='store_true', help='Send sfz to stdout instead.')
parser.add_argument('-k', '--noknobs', dest="noknobs", action='store_true', help='Remove knobs.')
parser.add_argument('-v', '--verbose', dest="verbose", action='store_true', help='Print feedback during processing.')
parser.add_argument('-e', '--nodecor', dest="nodecor", action='store_true', help="Don't decorate sfz with comments.")
parser.add_argument('-o', '--out', dest="out", type=str, default=None, help='Output filename override (without sfz extension).')
parser.add_argument('-d', '--outdir', dest="outdir", type=str, default=None, help='Output directory override.')
parser.add_argument('-c', '--nocrossfade', dest="nocrossfade", action='store_true', help='Disable crossfade.')
parser.add_argument('-r', '--noreleases', dest="noreleases", action='store_true', help='Ignore release samples.')
parser.add_argument('-b', '--createbase', dest="createBasefile", action='store_true', help='Creates basic file with the "source" as name.')
parser.add_argument('-y', '--yamlformat', dest="helpFormat", action="store_true", help='Print YAML format help.')
parser.add_argument('-f', '--force', dest="force", action="store_true", help="Don't process soundwaves.")
parser.add_argument('source', help="Source YAML file.")
args = parser.parse_args()

if args.createBasefile:
	try:
		with open(args.source + ".yaml", "w", encoding="utf-8") as f:
			data = dump({"output":"Instrument", "layers":{"sustain":{"source":'', "filter":''}}}, allow_unicode=True, encoding=None, Dumper=Dumper)
			f.write(data)
		sys.exit(0)
	except:
		print("Failed to open output file.", file=sys.stderr)
		sys.exit(-1)

try:
	with open(args.source, "r", encoding="utf-8") as f:
		data = load(f, Loader=Loader)
except:
	print("Failed to open source file.", file=sys.stderr)
	sys.exit(-1)

info = sys.stdout if args.verbose else open(os.devnull, "w")	

#	------------------------------------------------------------

#	------------------------------------------------------------

outputName = args.out if args.out else data["output"]
outputDir = args.outdir if args.outdir else "."

commentData = data["comment"] if "comment" in data else None

globalLayer = Global(data)

if "sustain" in data and "layers" not in data:	
	layers = [Layer("sustain", data["sustain"])]
else:
	layers = [Layer(a,b) for (a,b) in data["layers"].items()]

#	------------------------------------------------------------

#	------------------------------------------------------------

def dynToInt(dyn: str) -> int:
	if dyn.startswith('p'):
		return -len(dyn)
	if dyn == "mp":
		return 0
	if dyn == "mf":
		return 1
	if dyn.startswith("f"):
		return len(dyn)+1
	return int(R_num.search(dyn).group(0))


def parseNote(layer:Layer, filename: str, parsed: str):
	fcs = layer.split.split(parsed)
	index = -255
	dyn = 0
	rr = 0
	for fc in fcs:
		f = fc.lower()
		if f in globalLayer.map:
			f = globalLayer.map[f]

		if f in layer.map:
			f = layer.map[f]

		if (m := R_note.match(f)):
			index = noteNames[m.group(1)]
			if m.group(2):
				index += 1 if m.group(2) == '#' else -1
			index += int(m.group(3)) * 12
		elif R_dyn.match(f):
			dyn = dynToInt(f)
		elif R_num.match(f):
			index = int(f)*layer.stride - layer.indexOffset
		elif m := R_rr.match(f):
			rr = int(m.group(1))

	if index == -255:
		if layer.onekey:
			print(filename, file=info)
			layer.dynamics[dyn][60][rr] = Sample(filename)
			return
		if layer.unpitched:
			print(filename, file=info)
			index = len(layer.dynamics[dyn])
			layer.dynamics[dyn][index][rr] = Sample(filename)
			return

		print("// Unknown note: %s" % filename, file=info)
		return
	
	index += layer.octaveOffset * 12 + layer.transpose
	if index < 0:
		print("// Negative index: %s" % filename, file=info)
	else:
		print(filename, file=info)
		layer.dynamics[dyn][index][rr] = Sample(filename)
	

def scanLayer(layer:Layer):
	try:
		files = os.listdir(layer.srcDir)
	except:
		print(f"Failed to open specified layer directory: {layer.srcDir}", file=sys.stderr)
		return
	
	for filename in files:
		if not R_format.search(filename):
			continue

		parsed = R_format.sub(r"", filename)
		if globalLayer.filter and not globalLayer.filter.search(parsed):
			continue

		if layer.filter and not layer.filter.search(parsed):
			continue
		
		changed = False
		for rx, replacement in globalLayer.sub:
			parsed = rx.sub(replacement, parsed)
			changed = True
		for rx, replacement in layer.sub:
			parsed = rx.sub(replacement, parsed)
			changed = True
		
		if changed:
			print("// (Parsed: %s)" % parsed, file=info)
		parseNote(layer, filename, parsed)

#	------------------------------------------------------------

def analyzeLayers():
	"""Function for obtaining offset and volume for all samples."""
	
	if args.force or globalLayer.skipAnalysis:
		return
	
	try:
		import soundfile as sf
		import numpy as np
	except:
		print("Soundfile and Numpy libraries required for file analysis.\nConsider installing them using: python -m pip install soundfile numpy", file=sys.stderr)
		return

	def analyzeFile(layer: Layer, sample: Sample):
		data, rate = sf.read(os.path.join(layer.srcDir, sample.name))
		if len(data.shape) == 1: #mono
			amp = np.abs(data)
			smooth = np.convolve(amp, np.ones((100,))/100, mode='valid')
			cutoff = np.max(smooth)/50
			offset = np.min(np.where(smooth > cutoff))
			if offset > 100:
				sample.offset = offset-100
	
			sample.vol = np.percentile(smooth[offset:offset+rate], 95) - 4.5
			sample.vol = -10 * math.log10(sample.vol)
		else:
			amps = np.abs(data.swapaxes(0,1))
			smoothL = np.convolve(amps[0], np.ones((100,))/100, mode='valid')
			smoothR = np.convolve(amps[1], np.ones((100,))/100, mode='valid')
			cutoff = np.max(smoothR)/ 50
			offset = np.min(np.where(smoothR > cutoff))
			if offset > 100:
				sample.offset = offset-100

			volL = np.percentile(smoothL[offset:offset+rate], 95)
			volR = np.percentile(smoothR[offset:offset+rate], 95)
			sample.vol = -10 * math.log10(volL*volL + volR*volR) - 4.5

			# -- Pan can suffer for notes with low volume --
			# pan = math.atan2(volR, volL) * 400	#  0 -> L, 200pi -> R
			# sample.pan = pan/math.pi - 100 #   -100 -> L, 100   -> R
			# if sample.pan > 33 or sample.pan < -33:
			# 	sample.pan = 0

	for l in layers:
		if l.isRelease or l.skipAnalysis:
			continue
		for dyn in l.dynamics.values():
			for note in dyn.values():
				for sample in note.values():
					try:
						analyzeFile(l, sample)
						print(sample, file=info)
					except:
						print(f"Failed to open sample: {sample}", file=sys.stderr)

#	------------------------------------------------------------

#	------------------------------------------------------------

def printNote(layer: Layer, note: Sample, index, low, high, rr, rrLen):
	print('<region>', file=outfile)
	if rrLen > 1:
		print('seq_length=%d' % rrLen, file=outfile)
		print('seq_position=%d' % (rr+1), file=outfile)
	print('sample=%s' % os.path.relpath(os.path.join(layer.srcDir, note.name), outputDir), file=outfile)

	if layer.exact or (low == index and high == index):
		print('key=%s' % index, file=outfile)
	else:
		print('pitch_keycenter=%s' % index, file=outfile)
		if low:
			print('lokey=%d' % low, file=outfile)
		if high:
			print('hikey=%d' % high, file=outfile)
	if note.offset > 0:
		print('offset=%d' % note.offset, file=outfile)
	if note.pan != 0:
		print('pan=%d' % note.offset, file=outfile)
	if note.vol != 0:
		print('volume=%f' % note.vol + layer.volume, file=outfile)

	print(file=outfile)

#	------------------------------------------------------------

def printDynamic(layer: Layer, notes: dict, low, high, cc: int):
	print('<group>', file=outfile)
	if layer.attack > 0:
		print('ampeg_attack=%f' % layer.attack, file=outfile)

	if layer.isRelease:
		if layer.alwaysRelease:
			print("trigger=release_key", file=outfile)
		else:
			print("trigger=release", file=outfile)
		if globalLayer.knobs and not args.noknobs:
			print("gain_oncc205=10", file=outfile)

	if layer.unpitched:
		print("pitch_keytrack=0", file=outfile)

	if low:
		print('lovel=%d' % low, file=outfile)
	if high:
		print('hivel=%d' % high, file=outfile)
	
	if layer.volume != 0:
		print('volume=%f' % layer.volume, file=outfile)

	if layer.knob:
		print('xfin_locc%d=1 xfin_hicc%d=127' % (cc, cc), file=outfile)

	sortedRobins = sorted(notes.items())
	keys = sorted(notes)
	borders = [(keys[i] + keys[i+1])//2 for i in range(len(keys)-1)]

	print(file=outfile)

	for i,(index,robins) in enumerate(sortedRobins):
		rrln = len(robins)
		low = borders[i-1]+1 if i != 0 else None
		high = borders[i] if i != len(keys)-1 else None
		for j,(_, sample) in enumerate(sorted(robins.items())):
			if layer.min and layer.min > index:
				continue
			if layer.max and layer.max < index:
				continue
			printNote(layer, sample, index, low, high, j, rrln)

#	------------------------------------------------------------

def velBorder(layer: Layer, i, ln):
	return int((i/ln) ** layer.exponent * 128)

def printLayer(layer: Layer, li:int):
	dynLen = len(layer.dynamics)
	_sorted = sorted(layer.dynamics.items())[::(-1 if layer.invertDynamics else 1)]
	for i,(_,notes) in enumerate(_sorted):
		low = velBorder(layer, i, dynLen) if i != 0 else None
		high = velBorder(layer, i+1, dynLen)-1 if i != dynLen-1 else None
		printDynamic(layer, notes, low, high, 301+li)

def printCommentData(cm:dict):
	for k,v in cm.items():
		print("// %s: " % k, file=outfile)
		if type(v) is dict:
			printCommentData(v)
		else:
			print("// - %s" % v, file=outfile)
	print(file=outfile)

def printGlobal():
	if not args.noknobs:
		if globalLayer.knobs:
			print('<control>', file=outfile)
			print('label_cc72=Release', file=outfile)
			print('label_cc73=Attack', file=outfile)
			print('set_cc72=18    //Release = 128*.14 (14%)', file=outfile)
			print('set_cc73=0     //Attack = 0%', file=outfile)
			if not args.noreleases:
				print('label_cc205=Release Volume', file=outfile)
				print('set_cc205=60', file=outfile)
		for i,layer in enumerate(layers):
			if layer.knob:
				print('label_cc%d=%s' % (301+i, layer.name), file=outfile)
				print('set_cc%d=%d' % (301+i, layer.knobVal), file=outfile)
		print(file=outfile)

	print('<global>', file=outfile)
	print('ampeg_attack=%f' % globalLayer.attack, file=outfile)
	print('ampeg_release=%f' % globalLayer.release, file=outfile)

	if not args.noknobs and globalLayer.knobs:
		print('ampeg_release_oncc72=6  //on Release', file=outfile)
		print('ampeg_attack_oncc73=6  //on Attack', file=outfile)
	print(file=outfile)
		

def printInstrument():
	if not args.nodecor:
		print('// Instrument: %s' % globalLayer.name, file=outfile)
		print(file=outfile)
		print('// Settings used: %s' % str(data), file=outfile)
		print(file=outfile)
		if commentData:
			printCommentData(commentData)
	
	printGlobal()
	for li,layer in enumerate(layers):
		if args.noreleases and layer.isRelease:
			continue
		printLayer(layer, li)

#	------------------------------------------------------------

#	------------------------------------------------------------

for layer in layers:
	scanLayer(layer)

analyzeLayers()

try:
	outfile = sys.stdout if args.stdout else open("%s.sfz" % outputName, "w", encoding="utf-8")
except:
	print("Failed to open output file: ", file=sys.stderr)
	sys.exit(-1)

printInstrument()

try:
	if outfile != sys.stdout:
		outfile.close()
	if info != sys.stdout:
		info.close()
except:
	pass
