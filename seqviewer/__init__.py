import sys
import ab1
import numpy
import contextlib

def base_color(base):
    base_coloring = {'A': 'green', 'C': 'blue', 'T': 'red', 'G': 'black'}
    try:
        return base_coloring[base]
    except KeyError:
        return 'yellow'


class SequenceTrack(object):
    def __init__(self, sequence, name="(sequence)", offset=0):
        self.sequence = sequence
        self.offset = 0
        self.name = name
    def render_row(self, limit=None):
        xml = """<div class="track sequence">"""
        for i in range(self.offset):
            xml += """<div class="track-entry"></div>"""
        for i in range(limit==None and len(self) or limit):
            xml += self.render(i)
        xml += """</div>"""
        return xml
    def render(self, i):
        base = self.sequence[i]
        return """<div class="track-entry %d" style="color: %s">%s</div>""" % \
            (i, base_color(base), base)
    def __getitem__(self, i):
        return self.render(i)
    def __str__(self):
        return """SequenceTrack("%s")""" % (self.sequence)
    def __len__(self):
        return len(self.sequence)


class IntegerTrack(object):
    def __init__(self, sequence, name="(integers)", offset=0):
        self.sequence = sequence
        self.offset = offset
        self.name = name
    def render_row(self, limit=None):
        xml = """<div class="track integer">"""
        for i in range(self.offset):
            xml += """<div class="track-entry"></div>"""
        for i in range(limit==None and len(self) or limit):
            xml += self.render(i)
        xml += """</div>"""
        return xml
    def render(self, i):
        val = self.sequence[i]
        return """<div class="track-entry %d">%d</div>""" % (i, val)
    def __getitem__(self, i):
        return self.render(i)
    def __str__(self):
        return """IntegerTrack(%s)""" % (repr(self.sequence))
    def __len__(self):
        return len(self.sequence)

def close_enough(Lx,Ly, Rx,Ry, px,py):
    """Is px,py close enough to the line given by L and R to be approximated by it?"""
    # Find the vertical distance of px,py from the line through Lx,Ly
    # and Rx,Ry.  px,py is defined to be "close enough" if it no more
    # than a fraction alpha of the average height of the line away
    # from it.  The value of alpha here was selected by looking at the
    # output by eye and taking the highest value that left the curves
    # still looking reasonably smooth.
    alpha = 0.005
    return abs(py - ((Ry-Ly)/float(Rx-Lx))*(px-Lx) - Ly) < alpha * (Ly + Ry)/2.0

def cutoff(a, n_hinges=6.1):
    m = numpy.median(numpy.log(a+1))
    h = sorted(numpy.log(a+1))[int(0.75*len(a))]
    d = h-m
    c = numpy.exp(m + n_hinges*d) - 1
    return c


class ChromatogramTrack(object):
    def __init__(self, A, C, T, G, centers, name="(chromatogram)", offset=0):
        self.name = name
        self.offset = offset
        assert len(A) == len(C)
        assert len(A) == len(T)
        assert len(A) == len(G)
        assert len(centers) < len(A)
        assert centers[-1] < len(A)
        self.A = numpy.array(A).astype(numpy.float)
        self.C = numpy.array(C).astype(numpy.float)
        self.G = numpy.array(G).astype(numpy.float)
        self.T = numpy.array(T).astype(numpy.float)
        all_traces = numpy.concatenate([self.A,self.C,self.T,self.G])
        self.max_value = min(max(all_traces), cutoff(all_traces))

        self.centers = numpy.array(centers)

        self.boundaries = numpy.zeros(len(centers)+1)
        self.boundaries[1:-1] = (self.centers[1:] + self.centers[:-1])/2.0
        self.boundaries[-1] = len(A)-1

        # self.Qx = numpy.array([i+1/3.0 for i in range(len(A)-1)])
        # self.Px = numpy.array([i+2/3.0 for i in range(len(A)-1)])

        # self.Py = dict([(b, qs(self.trace(b)))
        #                 for b in 'ACTG'])
        # self.Qy = dict([(b, ps_to_qs(self.Py[b], self.trace(b)))
        #                 for b in 'ACTG'])

    def render_row(self, limit=None):
        xml = """<div class="track chromatogram">"""
        for i in range(self.offset):
            xml += """<div class="track-entry"></div>"""
        for i in range(limit==None and len(self) or limit):
            xml += self.render(i)
        xml += """</div>"""
        return xml

    def render(self, i):
        left = int(self.boundaries[i])
        right = int(self.boundaries[i+1])
        assert left < self.centers[i]
        assert right > self.centers[i]
        width = float(right-left)
        xml = """<div class="track-entry %d"><div class="svg-container">
                   <svg preserveAspectRatio="none" viewbox="0 -0.05 1 1.05" version="1.1">""" % i
        start = max(left-1, 0)
        end = min(right, len(self.trace('A'))-1)
        m = self.max_value
        for b in 'ACTG':
            path = "M%1.2f,%1.2f" % ((start-left)/width,
                                     1-self.trace(b)[start]/m)
            i = start
            while i < end:
                Lx, Ly, Rx, Ry = \
                    (i-left)/width, 1-self.trace(b)[i]/m, \
                    (i+1-left)/width, 1-self.trace(b)[i+1]/m

                # This code sparsifies the lines in the SVG: any
                # points that can be approximated adequately (as
                # defined by the function close_enough) by just
                # passing a line on through are omitted.  This makes a
                # huge difference: the HTML output of the example
                # trace file I'm working with drops from 14.4kb to
                # 5.1kb with this code in place.  The rendering time
                # in Firefox goes from 9s to under 7s.

                # It's also important that I generate a single path
                # per trace instead of a bunch of separate line
                # elements.  This drops the file size another factor
                # of 5, and decreases the rendering time to trivial (~0.7s).

                # Next, try to shrink the names a bit.

                skipped = []
                while i+1 < end:
                    nextx, nexty = (i+2-left)/width, 1-self.trace(b)[i+2]/m
                    if all([close_enough(Lx,Ly,nextx,nexty,px,py)
                            for px,py in skipped + [(Rx,Ry)]]):
                        skipped += [(Rx,Ry)]
                        Rx, Ry = nextx, nexty
                        i += 1
                    else:
                        break
                path += """L%1.2f,%1.2f""" % (Rx, Ry)
                i += 1
            xml += """<path stroke-width="0.01" stroke="%s" fill="none" d="%s" />""" % \
                (base_color(b), path)
        xml += "</svg></div></div>"
        return xml
    def trace(self, base):
        if base == 'A':
            return self.A
        elif base == 'C':
            return self.C
        elif base == 'T':
            return self.T
        elif base == 'G':
            return self.G
        else:
            raise ValueError('Invalid base: %s' % base)
    def __getitem__(self, i):
        return self.render(i)
    def __str__(self):
        return "ChromatogramTrack"
    def __len__(self):
        return len(self.centers)

@contextlib.contextmanager
def liftW(x):
    yield x


def ab1_to_tracks(handle_or_filename):
    with isinstance(handle_or_filename, basestring) and \
            open(handle_or_filename, 'rb') or \
            liftW(handle_or_filename) as handle:
        a = ab1.Ab1File(handle)
        bases = SequenceTrack(a.bases(), name='Bases')
        confidences = IntegerTrack(a.base_confidences(), name='Confidence')
        chromatogram = ChromatogramTrack(A=a.trace('A'),
                                         C=a.trace('C'),
                                         T=a.trace('T'),
                                         G=a.trace('G'),
                                         centers=a.base_centers(),
                                         name='Trace')
        return [bases,confidences,chromatogram]



def htmlize(tracks, spacing):
    pass

def fasta_to_track(handle_or_filename):
    pass

