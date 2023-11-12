# SFZGen
Sforzando file generator.

This script uses a YAML preset and instrument soundwave files to directly generate a .sfz instrument.

It is a work in progress.

## Usage

> `python sfzGen.py source.yaml [options]`

### Options:
	-x, --stdout      - Send sfz to stdout instead.
	-k, --noknobs     - Remove knobs.
	-v, --verbose     - Print feedback during processing.
	-e, --nodecor     - Don't decorate sfz with comments.
	-o, --out         - Output filename override (without sfz extension).
	-d, --outdir      - Output directory override.
	-c, --nocrossfade - Disable crossfade.
	-r, --noreleases  - Ignore release samples.
	-b, --createbase  - Creates basic file with the "source" as name.
	-y, --yamlformat  - Print YAML format help.
	-f, --force       - Don't process soundwaves.

## YAML preset format

This script uses a YAML preset file for generation. It's options are split into:
- **Global settings** - applied to all layers
- **Layer settings** - applied to individual layers

### Global settings:

#### Main settings
	output   - output file name without extension.
	comment  - dictionary of arbitrary values

#### Layers
	sustain - layer element, see Layer settings.
	# or
	layers:	#dictionary of layers.
		a:
			...
		release:
			...

#### Envelope
	volume   - added to layer volumes.
	attack   - default 0.004
	release  - default 0.3
	exponent - velocity exponent, applied to even distribution of transitions from 0-1 (0-127)

#### Indexing
	min      - minimum index. Notes outside range are ignored. No default.
	max      - maximum index. No default.
	octaveOffset
	transpose
	middleC  - index of middle C for indexed naming. (Default: 60)
	stride   - index step. (Default: 1)

#### Switches
	crossfade      - Crossfade based on key.
	unpitched      - Don't vary pitch based on key.
	invertDynamics - Invert order of dynamics.
	exact          - Won't extend note key ranges, possibly leaving gaps.
	skipAnalysis   - Don't analyze any soundwaves. Equal to --force CLI option.
	knobs - Create Attack, Release and Release Volume controls, if present.

#### Filtering
	Editing - filter, sub, map - see Layer settings.

### Local settings

	isRelease     - release layer. Can just be named "release" for same effect.
	alwaysRelease - triggered on note up regardless of sustain pedal.
	
	onekey        - only one note on given layer. Doesn't need an identifiable index. Can have RRs.
	
	knob          - create volume knob. Labeled based on layer name.
	knobPercent   - default value of knob. 0-100 integer.

#### Filtering
These options are processed after global filters:

	filter        - Regex. Only matches get processed further (anywhere in filename).   Case sensitive.
	sub           - List of from-to regexes. Applied to whole filename.                 Case sensitive.
	split         - Regex. Splits filename into chunks.                                 Case sensitive.
	map           - Dictionary of key-replacement elements. Applied to chunks.          Case INsensitive.

#### Additive to global
	volume    -
	octave    -
	transpose -
	
#### Replace global settings
	attack   -
	release  -
	min      -
	max      -
	middleC  -
	stride   -
	exponent -

#### Replaced by global settings
	crossfade      - 
	unpitched      - 
	invertDynamics - 
	exact          - 
	skipAnalysis   - Don't analyze soundwaves for layer.

## License

This script is published under the MIT license.