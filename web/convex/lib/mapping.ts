// IPC-to-BNS Mapping, ported from ingestion/mapping.py. A structured lookup,
// deliberately NOT a Source of Truth: never chunked, embedded, or loaded into
// the vector store. It exists only to recognise a repealed IPC number on
// input and annotate the current BNS section on output.
//
// The mapping data itself is bundled from data/ipc_bns_mapping.json at build
// time; the source file stays the single authority.
import mappingJson from "../../../data/ipc_bns_mapping.json";

export type MappingEntry = {
  ipc: string;
  bns: string;
  label: string;
};

export class IpcBnsMapping {
  private entries: Map<string, MappingEntry>;

  constructor(entries: Map<string, MappingEntry>) {
    this.entries = entries;
  }

  lookup(ipcSection: string): MappingEntry | null {
    return this.entries.get(ipcSection.trim().toUpperCase()) ?? null;
  }

  // True iff every pinned IPC->BNS pair in the chart is reproduced.
  verify(officialChart: Record<string, string>): boolean {
    return Object.entries(officialChart).every(([ipc, bns]) => {
      const entry = this.lookup(ipc);
      return entry !== null && entry.bns === bns;
    });
  }

  get size(): number {
    return this.entries.size;
  }
}

export function mappingFromEntries(
  raw: Array<{ ipc: string; bns: string; label: string }>,
): IpcBnsMapping {
  return new IpcBnsMapping(
    new Map(
      raw.map((e) => [
        e.ipc.toUpperCase(),
        { ipc: e.ipc.toUpperCase(), bns: e.bns, label: e.label },
      ]),
    ),
  );
}

// The bundled production mapping (data/ipc_bns_mapping.json).
export function loadIpcBnsMapping(): IpcBnsMapping {
  return mappingFromEntries(
    (mappingJson as { entries: Array<{ ipc: string; bns: string; label: string }> })
      .entries,
  );
}
