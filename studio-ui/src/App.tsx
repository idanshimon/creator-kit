import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from './lib/api';
import type { AppState, Asset, Job, Project } from './lib/api';
import type { Clip, Plan } from './lib/timeline';
import { clampSpeed, clampVolume, moveClip, splitClipAt } from './lib/timeline';
import { TopBar } from './components/TopBar';
import { AssetPanel } from './components/AssetPanel';
import { SourcePreview } from './components/SourcePreview';
import { Timeline } from './components/Timeline';
import { ClipInspector } from './components/ClipInspector';
import { OutputSettings } from './components/OutputSettings';
import { ExportPanel } from './components/ExportPanel';

// id generator for client-minted clip ids (opaque, unique within a session)
let idc = 0;
const mkid = (suffix = '') => `clip_${Date.now().toString(36)}_${(idc++).toString(36)}${suffix ? '_' + suffix : ''}`;

export function App() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [projects, setProjects] = useState<AppState['projects']>([]);
  const [jobs, setJobs] = useState<Job[]>([]);

  const [project, setProject] = useState<Project | null>(null);
  // Working copy of the plan (edits live here until Save).
  const [plan, setPlan] = useState<Plan | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [dirty, setDirty] = useState(false);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  // ---- state / polling ----
  const refreshState = useCallback(async () => {
    try {
      const s = await api.getState();
      setProjects(s.projects);
      setAssets(s.assets);
      setJobs(s.jobs);
    } catch (e: any) {
      setError(e?.message || 'Failed to load state');
    }
  }, []);

  useEffect(() => {
    refreshState();
    const t = setInterval(refreshState, 3000); // poll real jobs/assets/projects
    return () => clearInterval(t);
  }, [refreshState]);

  // Detect a newer revision landing server-side while we hold an older one.
  useEffect(() => {
    if (!project) return;
    const summary = projects.find((p) => p.id === project.id);
    if (summary && summary.revision > project.revision) setStale(true);
  }, [projects, project]);

  const loadProject = useCallback(async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const p = await api.getProject(id);
      setProject(p);
      setPlan(clonePlan(p.plan));
      setSelectedId(p.plan.clips[0]?.id ?? null);
      setDirty(false);
      setStale(false);
    } catch (e: any) {
      setError(e?.message || 'Failed to open project');
    } finally {
      setBusy(false);
    }
  }, []);

  function guardDiscard(): boolean {
    if (dirtyRef.current) return window.confirm('Discard unsaved changes?');
    return true;
  }

  // ---- plan mutations (local, mark dirty) ----
  const mutate = useCallback((fn: (p: Plan) => Plan) => {
    setPlan((prev) => (prev ? fn(prev) : prev));
    setDirty(true);
  }, []);

  const clips = plan?.clips ?? [];
  const selectedIndex = clips.findIndex((c) => c.id === selectedId);
  const selectedClip = selectedIndex >= 0 ? clips[selectedIndex] : null;
  const selectedAsset = selectedClip ? assets.find((a) => a.id === selectedClip.asset_id) ?? null : null;

  const addAsset = (asset: Asset) => {
    const clip: Clip = {
      id: mkid(),
      asset_id: asset.id,
      in: 0,
      out: asset.duration,
      speed: 1,
      volume: 1,
      mute: false,
    };
    mutate((p) => ({ ...p, clips: [...p.clips, clip] }));
    setSelectedId(clip.id);
  };

  const patchClip = (patch: Partial<Clip>) => {
    if (!selectedClip) return;
    if (patch.speed !== undefined) patch.speed = clampSpeed(patch.speed);
    if (patch.volume !== undefined) patch.volume = clampVolume(patch.volume);
    mutate((p) => ({
      ...p,
      clips: p.clips.map((c) => (c.id === selectedClip.id ? { ...c, ...patch } : c)),
    }));
  };

  const setIn = (t: number) => {
    if (!selectedClip) return;
    patchClip({ in: Math.min(Math.max(0, t), selectedClip.out - 0.05) });
  };
  const setOut = (t: number) => {
    if (!selectedClip) return;
    patchClip({ out: Math.max(t, selectedClip.in + 0.05) });
  };

  const splitAt = (index: number, sourceTime: number) => {
    mutate((p) => ({ ...p, clips: splitClipAt(p.clips, index, sourceTime, (s) => mkid(s)) }));
  };
  const splitSelectedAtPlayhead = (t: number) => {
    if (selectedIndex >= 0) splitAt(selectedIndex, t);
  };
  const splitMidpoint = (index: number) => {
    const c = clips[index];
    if (c) splitAt(index, (c.in + c.out) / 2);
  };

  const duplicate = (index: number) => {
    const c = clips[index];
    if (!c) return;
    const copy = { ...c, id: mkid('dup') };
    mutate((p) => {
      const next = p.clips.slice();
      next.splice(index + 1, 0, copy);
      return { ...p, clips: next };
    });
    setSelectedId(copy.id);
  };

  const move = (index: number, delta: number) => mutate((p) => ({ ...p, clips: moveClip(p.clips, index, delta) }));
  const remove = (index: number) => {
    const removed = clips[index];
    mutate((p) => ({ ...p, clips: p.clips.filter((_, i) => i !== index) }));
    if (removed?.id === selectedId) setSelectedId(null);
  };

  const patchPlan = (patch: Partial<Plan>) => mutate((p) => ({ ...p, ...patch }));

  // ---- project ops ----
  const newProject = async () => {
    if (!guardDiscard()) return;
    const name = window.prompt('New project name:');
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.createProject(name);
      await refreshState();
      setProject(p);
      setPlan(clonePlan(p.plan));
      setSelectedId(p.plan.clips[0]?.id ?? null);
      setDirty(false);
      setStale(false);
    } catch (e: any) {
      setError(e?.message || 'Failed to create project');
    } finally {
      setBusy(false);
    }
  };

  const rename = (name: string) => {
    setProject((p) => (p ? { ...p, name } : p));
    setDirty(true);
  };

  const save = async () => {
    if (!project || !plan) return;
    setBusy(true);
    setError(null);
    try {
      const label = window.prompt('Revision label:', 'edit') || 'edit';
      const p = await api.saveProject(project.id, {
        name: project.name,
        plan,
        expected_revision: project.revision,
        label,
      });
      setProject(p);
      setPlan(clonePlan(p.plan));
      setDirty(false);
      setStale(false);
      await refreshState();
    } catch (e: any) {
      if (e instanceof ApiError && e.stale) setStale(true);
      setError(e?.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  };

  const undo = async () => {
    if (!project) return;
    if (dirty && !guardDiscard()) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.undo(project.id, project.revision);
      applyServerProject(p);
    } catch (e: any) {
      if (e instanceof ApiError && e.stale) setStale(true);
      setError(e?.message || 'Undo failed');
    } finally {
      setBusy(false);
    }
  };

  const redo = async () => {
    if (!project) return;
    if (dirty && !guardDiscard()) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.redo(project.id, project.revision);
      applyServerProject(p);
    } catch (e: any) {
      if (e instanceof ApiError && e.stale) setStale(true);
      setError(e?.message || 'Redo failed');
    } finally {
      setBusy(false);
    }
  };

  function applyServerProject(p: Project) {
    setProject(p);
    setPlan(clonePlan(p.plan));
    setDirty(false);
    setStale(false);
    refreshState();
  }

  const doRender = async (kind: 'draft' | 'final') => {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      await api.render(project.id, kind, project.revision);
      await refreshState();
    } catch (e: any) {
      if (e instanceof ApiError && e.stale) setStale(true);
      setError(e?.message || 'Render request failed');
    } finally {
      setBusy(false);
    }
  };

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      await api.uploadAsset(file);
      await refreshState();
    } catch (e: any) {
      setError(e?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const selectProject = (id: string) => {
    if (id && guardDiscard()) loadProject(id);
  };

  // ---- keyboard shortcuts (skip when typing) ----
  useEffect(() => {
    const isTyping = (t: EventTarget | null) => {
      const el = t as HTMLElement | null;
      if (!el) return false;
      const tag = el.tagName;
      return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
    };
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      const k = e.key.toLowerCase();
      if (k === 's') {
        e.preventDefault();
        if (dirty && !stale && project) save();
      } else if (k === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (project?.can_undo) undo();
      } else if ((k === 'z' && e.shiftKey) || k === 'y') {
        e.preventDefault();
        if (project?.can_redo) redo();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // Warn before unloading with unsaved edits.
  useEffect(() => {
    const beforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, []);

  const projectForUi = useMemo(() => (project && plan ? { ...project, plan } : project), [project, plan]);

  return (
    <div className="app">
      <TopBar
        projects={projects}
        project={projectForUi}
        dirty={dirty}
        stale={stale}
        busy={busy}
        onSelect={selectProject}
        onNew={newProject}
        onRename={rename}
        onSave={save}
        onUndo={undo}
        onRedo={redo}
        onReload={() => project && loadProject(project.id)}
      />

      <div className="workspace">
        <AssetPanel assets={assets} uploading={uploading} onUpload={upload} onAdd={addAsset} />

        <div className="panel stage" style={{ borderLeft: 'none' }}>
          {error && (
            <div className="alert" style={{ margin: 10 }}>
              {error}
              <button className="btn ghost sm" onClick={() => setError(null)}>
                dismiss
              </button>
            </div>
          )}
          {!project ? (
            <div className="preview-wrap">
              <span className="preview-empty">Select or create a project to start editing.</span>
            </div>
          ) : (
            <>
              <SourcePreview
                clip={selectedClip}
                asset={selectedAsset}
                onSetIn={setIn}
                onSetOut={setOut}
                onSplitAtPlayhead={splitSelectedAtPlayhead}
              />
              <Timeline
                clips={clips}
                assets={assets}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onMove={move}
                onDuplicate={duplicate}
                onSplit={splitMidpoint}
                onRemove={remove}
              />
            </>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <span>Inspector</span>
          </div>
          <div className="panel-body">
            {project && plan ? (
              <>
                <ClipInspector clip={selectedClip} onPatch={patchClip} />
                <div className="divider" />
                <OutputSettings plan={plan} onPatch={patchPlan} />
                <div className="divider" />
                <ExportPanel project={project} jobs={jobs} dirty={dirty} busy={busy} onRender={doRender} />
              </>
            ) : (
              <div className="muted">No project open.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function clonePlan(plan: Plan): Plan {
  return {
    ...plan,
    clips: (plan.clips || []).map((c) => ({ ...c })),
  };
}
