from django import forms
from .models import Airport, Route
import heapq

class AirportForm(forms.ModelForm):
    class Meta:
        model = Airport
        fields = ["code", "name"]

class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ["source", "destination", "distance_km", "duration_min"]
        widgets = {
            "distance_km": forms.NumberInput(attrs={"step": "0.1"}),
        }

class RouteByCodeForm(forms.Form):
    source_code = forms.CharField(max_length=10, label="Source airport code")
    destination_code = forms.CharField(max_length=10, label="Destination airport code")
    position = forms.FloatField(label="Position", min_value=0)
    duration = forms.IntegerField(label="Duration (minutes)", min_value=0)

    def clean(self):
        cleaned = super().clean()
        src_code = cleaned.get("source_code")
        dst_code = cleaned.get("destination_code")
        if not src_code or not dst_code:
            return cleaned
        try:
            src = Airport.objects.get(code__iexact=src_code.strip())
        except Airport.DoesNotExist:
            raise forms.ValidationError({"source_code": "Source airport not found."})
        try:
            dst = Airport.objects.get(code__iexact=dst_code.strip())
        except Airport.DoesNotExist:
            raise forms.ValidationError({"destination_code": "Destination airport not found."})
        if src == dst:
            raise forms.ValidationError("Source and destination must be different.")
        # Prevent duplicate routes
        if Route.objects.filter(source=src, destination=dst).exists():
            raise forms.ValidationError("This route already exists.")
        cleaned["source"] = src
        cleaned["destination"] = dst
        return cleaned

    def save(self):
        data = self.cleaned_data
        route = Route.objects.create(
            source=data["source"],
            destination=data["destination"],
            distance_km=data["position"],
            duration_min=data["duration"],
        )
        return route

class CombinedAirportRouteForm(forms.Form):
    parent_code = forms.CharField(max_length=10, label="Source airport code", initial="A")
    child_code = forms.CharField(max_length=10, label="Destination airport code")
    POSITION_LEFT = 'LEFT'
    POSITION_RIGHT = 'RIGHT'
    position = forms.ChoiceField(choices=((POSITION_LEFT, 'Left'), (POSITION_RIGHT, 'Right')), label="Position")
    duration = forms.IntegerField(label="Duration (minutes)", min_value=0)
    distance_km = forms.FloatField(label="Distance (km)", min_value=0)

    MASTER_CODE = "A"

    def clean_parent_code(self):
        code = self.cleaned_data["parent_code"].strip().upper()
        if not code:
            raise forms.ValidationError("Source code is required")
        return code

    def clean_child_code(self):
        code = self.cleaned_data["child_code"].strip().upper()
        if not code:
            raise forms.ValidationError("Child code is required")
        return code

    def clean(self):
        cleaned = super().clean()
        # Use selected source (defaults to 'A')
        parent_code = cleaned.get("parent_code")
        child_code = cleaned.get("child_code")
        if not parent_code or not child_code:
            return cleaned
        # Resolve or create parent/child airports
        parent = Airport.objects.filter(code__iexact=parent_code).first()
        if parent is None:
            parent = Airport.objects.create(code=parent_code, name=("Master" if parent_code == self.MASTER_CODE else parent_code))
        if parent_code == child_code:
            raise forms.ValidationError("Parent and child cannot be the same airport.")
        child = Airport.objects.filter(code__iexact=child_code).first()
        # Check position availability on parent (only one LEFT and one RIGHT per parent)
        pos = cleaned.get('position')
        if pos and Route.objects.filter(source=parent, position=pos).exists():
            raise forms.ValidationError({"position": "This position is already used for the parent airport."})
        # Check duplicate edge
        if child and Route.objects.filter(source=parent, destination=child).exists():
            raise forms.ValidationError("This route already exists.")
        cleaned["_parent"] = parent
        cleaned["_existing_child"] = child
        return cleaned

    def save(self):
        data = self.cleaned_data
        parent = data["_parent"]
        child = data.get("_existing_child")
        if child is None:
            child = Airport.objects.create(code=data["child_code"], name=data["child_code"])
        route = Route.objects.create(
            source=parent,
            destination=child,
            position=data["position"],
            duration_min=data["duration"],
            distance_km=data["distance_km"],
        )
        return child, route


class NthNodeSearchForm(forms.Form):
    OP_NTH_LEFT = 'nth_left'
    OP_NTH_RIGHT = 'nth_right'
    OP_LONGEST = 'longest'
    OP_SHORTEST = 'shortest'
    OP_SHORTEST_BETWEEN = 'shortest_between'

    OPERATIONS = (
        (OP_NTH_LEFT, 'Nth Left'),
        (OP_NTH_RIGHT, 'Nth Right'),
        (OP_LONGEST, 'Longest (by duration, from base)'),
        (OP_SHORTEST, 'Shortest (by duration, from base)'),
        (OP_SHORTEST_BETWEEN, 'Shortest (by duration) between two airports'),
    )

    base_code = forms.CharField(max_length=10, label="Base airport code", initial="A")
    operation = forms.ChoiceField(choices=OPERATIONS)
    n = forms.IntegerField(min_value=1, required=False, label="N (for Nth ops)")
    src_code = forms.CharField(max_length=10, required=False, label="Source airport (for between)")
    dst_code = forms.CharField(max_length=10, required=False, label="Destination airport (for between)")

    def clean_base_code(self):
        code = self.cleaned_data['base_code'].strip().upper()
        if not code:
            raise forms.ValidationError('Base code is required')
        return code

    def clean(self):
        cleaned = super().clean()
        op = cleaned.get('operation')
        n = cleaned.get('n')
        if op in {self.OP_NTH_LEFT, self.OP_NTH_RIGHT} and not n:
            self.add_error('n', 'N is required for Nth operations')
        if op == self.OP_SHORTEST_BETWEEN:
            if not cleaned.get('src_code'):
                self.add_error('src_code', 'Source airport is required')
            if not cleaned.get('dst_code'):
                self.add_error('dst_code', 'Destination airport is required')
        return cleaned

    def perform(self):
        """
        Returns a dict with keys:
          - base: Airport
          - neighbors: list[(Airport, Route)] sorted by destination code
          - result: Optional[(Airport, Route)] for nth ops
          - best: Optional[(Airport, Route)] for longest/shortest
        """
        base = Airport.objects.filter(code__iexact=self.cleaned_data['base_code']).first()
        if base is None:
            raise forms.ValidationError({'base_code': 'Base airport not found.'})
        op = self.cleaned_data['operation']
        # neighbors view (for reference)
        qs = (Route.objects.filter(source=base)
              .select_related('destination')
              .order_by('destination__code'))
        neighbors = [(r.destination, r) for r in qs]
        data = {'base': base, 'neighbors': neighbors, 'result': None, 'best': None}

        if op in {self.OP_NTH_LEFT, self.OP_NTH_RIGHT}:
            n = self.cleaned_data['n']
            current = base
            for _ in range(n):
                wanted_pos = Route.POSITION_LEFT if op == self.OP_NTH_LEFT else Route.POSITION_RIGHT
                try:
                    step = Route.objects.select_related('destination').get(source=current, position=wanted_pos)
                except Route.DoesNotExist:
                    raise forms.ValidationError('Path breaks before reaching N steps.')
                current = step.destination
            data['result'] = (current, step)
            return data

        if op == self.OP_LONGEST:
            best_route = (Route.objects
                          .filter(source=base)
                          .select_related('destination')
                          .order_by('-duration_min')
                          .first())
            if not best_route:
                raise forms.ValidationError('No outgoing routes from the base airport.')
            data['best'] = (best_route.destination, best_route)
            return data

        if op == self.OP_SHORTEST:
            best_route = (Route.objects
                          .filter(source=base)
                          .select_related('destination')
                          .order_by('duration_min')
                          .first())
            if not best_route:
                raise forms.ValidationError('No outgoing routes from the base airport.')
            data['best'] = (best_route.destination, best_route)
            return data

        if op == self.OP_SHORTEST_BETWEEN:
            src_code = (self.cleaned_data.get('src_code') or '').strip().upper()
            dst_code = (self.cleaned_data.get('dst_code') or '').strip().upper()
            src = Airport.objects.filter(code__iexact=src_code).first()
            dst = Airport.objects.filter(code__iexact=dst_code).first()
            if not src or not dst:
                raise forms.ValidationError('Source or Destination airport not found.')
            # Dijkstra on directed graph by duration_min
            adj = {}
            for r in Route.objects.select_related('source', 'destination').all():
                adj.setdefault(r.source_id, []).append((r.destination_id, r.duration_min, r.id))
            dist = {src.id: 0}
            prev = {}
            edge_used = {}
            pq = [(0, src.id)]
            visited = set()
            while pq:
                d, u = heapq.heappop(pq)
                if u in visited:
                    continue
                visited.add(u)
                if u == dst.id:
                    break
                for v, w, edge_id in adj.get(u, []):
                    nd = d + w
                    if nd < dist.get(v, float('inf')):
                        dist[v] = nd
                        prev[v] = u
                        edge_used[v] = edge_id
                        heapq.heappush(pq, (nd, v))
            if dst.id not in dist:
                raise forms.ValidationError('No path found between the two airports.')
            # Reconstruct path as list of (Airport, Route)
            path_nodes = []
            cur = dst.id
            while cur != src.id:
                eid = edge_used[cur]
                r = Route.objects.select_related('source', 'destination').get(id=eid)
                path_nodes.append((r.destination, r))
                cur = prev[cur]
            path_nodes.reverse()
            data['path'] = path_nodes
            data['path_total_duration'] = dist[dst.id]
            return data

        return data
