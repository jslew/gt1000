import type { ChainElement } from "./api";

export type ChainNode = {
  id: string;
  label: string;
  shortLabel: string;
  detail: string | null;
  icon: string;
  enabled: boolean | null;
  reserved: boolean;
  output: boolean;
  routing: boolean;
};

export type ChainLayoutItem =
  | { kind: "arrow" }
  | { kind: "node"; node: ChainNode }
  | {
      kind: "split";
      divider: ChainNode;
      mixer: ChainNode;
      pathA: ChainNode[];
      pathB: ChainNode[];
    };

type LabelStyle = { icon: string; short: string };

const DIVIDER_RAW = new Set([35, 38, 41]);
const BRANCH_RAW = new Set([36, 39, 42]);
const MIXER_RAW = new Set([37, 40, 43]);

const CHAIN_STYLES: Record<string, LabelStyle> = {
  COMPRESSOR: { icon: "◎", short: "Comp" },
  "DISTORTION 1": { icon: "⚡", short: "Dist 1" },
  "DISTORTION 2": { icon: "⚡", short: "Dist 2" },
  "AIRD PREAMP 1": { icon: "🎸", short: "Preamp 1" },
  "AIRD PREAMP 2": { icon: "🎸", short: "Preamp 2" },
  "NOISE SUPPRESSOR 1": { icon: "⊘", short: "NS 1" },
  "NOISE SUPPRESSOR 2": { icon: "⊘", short: "NS 2" },
  "FX 1": { icon: "✦", short: "FX1" },
  "FX 2": { icon: "✦", short: "FX2" },
  "FX 3": { icon: "✦", short: "FX3" },
  "EQUALIZER 1": { icon: "≋", short: "EQ1" },
  "EQUALIZER 2": { icon: "≋", short: "EQ2" },
  "EQUALIZER 3": { icon: "≋", short: "EQ3" },
  "EQUALIZER 4": { icon: "≋", short: "EQ4" },
  CHORUS: { icon: "∿", short: "Chorus" },
  "DELAY 1": { icon: "⧖", short: "Dly1" },
  "DELAY 2": { icon: "⧖", short: "Dly2" },
  "DELAY 3": { icon: "⧖", short: "Dly3" },
  "DELAY 4": { icon: "⧖", short: "Dly4" },
  "MASTER DELAY": { icon: "⧖", short: "M.Dly" },
  "(RESERVED)": { icon: "·", short: "—" },
  REVERB: { icon: "◌", short: "Verb" },
  "FOOT VOLUME": { icon: "🦶", short: "F.Vol" },
  "PEDAL FX": { icon: "⌘", short: "P.FX" },
  "SEND/RETURN 1": { icon: "↔", short: "S/R1" },
  "SEND/RETURN 2": { icon: "↔", short: "S/R2" },
  LOOPER: { icon: "⟳", short: "Loop" },
  "SUB SP.SIMULATOR L": { icon: "🔈", short: "Sub SIM L" },
  "SUB SP.SIMULATOR R": { icon: "🔈", short: "Sub SIM R" },
  "MAIN SP.SIMULATOR L": { icon: "🔊", short: "Main SIM L" },
  "MAIN SP.SIMULATOR R": { icon: "🔊", short: "Main SIM R" },
  "BYPASS SUB L": { icon: "⏭", short: "Bp Sub L" },
  "BYPASS SUB R": { icon: "⏭", short: "Bp Sub R" },
  "BYPASS MAIN L": { icon: "⏭", short: "Bp Main L" },
  "BYPASS MAIN R": { icon: "⏭", short: "Bp Main R" },
  "DIVIDER 1": { icon: "⑂", short: "Div 1" },
  "DIVIDER 2": { icon: "⑂", short: "Div 2" },
  "DIVIDER 3": { icon: "⑂", short: "Div 3" },
  "BRANCH SPLIT1": { icon: "⑃", short: "Split" },
  "BRANCH SPLIT2": { icon: "⑃", short: "Split" },
  "BRANCH SPLIT3": { icon: "⑃", short: "Split" },
  "MIXER 1": { icon: "⊞", short: "Mix 1" },
  "MIXER 2": { icon: "⊞", short: "Mix 2" },
  "MIXER 3": { icon: "⊞", short: "Mix 3" },
  "SUB OUT L": { icon: "◁", short: "Sub L" },
  "SUB OUT R": { icon: "▷", short: "Sub R" },
  "MAIN OUT L": { icon: "◀", short: "Main L" },
  "MAIN OUT R": { icon: "▶", short: "Main R" },
};

const BLOCK_ID_STYLES: Record<string, LabelStyle> = {
  divider1: { icon: "⑂", short: "Div 1" },
  divider2: { icon: "⑂", short: "Div 2" },
  divider3: { icon: "⑂", short: "Div 3" },
  mixer1: { icon: "⊞", short: "Mix 1" },
  mixer2: { icon: "⊞", short: "Mix 2" },
  mixer3: { icon: "⊞", short: "Mix 3" },
  delay1: { icon: "⧖", short: "Dly1" },
  delay2: { icon: "⧖", short: "Dly2" },
  preamp1: { icon: "🎸", short: "Pre1" },
  preamp2: { icon: "🎸", short: "Pre2" },
  chorus: { icon: "∿", short: "Chorus" },
  reverb: { icon: "◌", short: "Verb" },
};

function abbreviateDisplayName(name: string): string {
  return name
    .replace(/SP\.SIMULATOR/gi, "SIM")
    .replace(/SIMULATOR/gi, "SIM")
    .replace(/SUPPRESSOR/gi, "Sup")
    .replace(/DISTORTION/gi, "Dist")
    .replace(/EQUALIZER/gi, "EQ")
    .replace(/PREAMP/gi, "Pre")
    .replace(/BRANCH SPLIT/gi, "Split")
    .replace(/DIVIDER/gi, "Div")
    .replace(/MIXER/gi, "Mix")
    .replace(/DELAY/gi, "Dly")
    .replace(/BYPASS/gi, "Bp")
    .replace(/\s+/g, " ")
    .trim();
}

function iconForCategory(name: string, blockId: string | null | undefined): string {
  const upper = name.toUpperCase();
  if (upper.includes("DIVIDER")) return "⑂";
  if (upper.includes("BRANCH") || upper.includes("SPLIT")) return "⑃";
  if (upper.includes("MIXER")) return "⊞";
  if (upper.includes("DELAY")) return "⧖";
  if (upper.includes("REVERB")) return "◌";
  if (upper.includes("OUT")) return "▣";
  if (upper.includes("BYPASS")) return "⏭";
  if (upper.includes("PREAMP") || blockId?.includes("preamp")) return "🎸";
  if (upper.includes("FX")) return "✦";
  if (upper.includes("EQ")) return "≋";
  return "●";
}

export function styleChainNode(
  displayName: string,
  detailBlockId?: string | null,
  typeName?: string | null,
): LabelStyle {
  const byName = CHAIN_STYLES[displayName];
  if (byName) {
    return byName;
  }
  if (detailBlockId) {
    const byBlock = BLOCK_ID_STYLES[detailBlockId];
    if (byBlock) {
      return byBlock;
    }
  }
  const short = abbreviateDisplayName(displayName);
  return { icon: iconForCategory(displayName, detailBlockId), short };
}

function isRoutingMarker(element: ChainElement): boolean {
  const raw = elementRawValue(element);
  if (raw != null && (DIVIDER_RAW.has(raw) || BRANCH_RAW.has(raw) || MIXER_RAW.has(raw))) {
    return true;
  }
  const name = (element.displayName ?? "").toUpperCase();
  return name.includes("DIVIDER") || name.includes("BRANCH") || name.includes("MIXER") || name.includes("SPLIT");
}

function elementRawValue(element: ChainElement): number | null {
  return typeof element.rawValue === "number" ? element.rawValue : null;
}

export function chainNodeFromElement(element: ChainElement, index: number): ChainNode {
  const label = element.displayName ?? "Unknown";
  const styled = styleChainNode(label, element.detailBlockID, element.typeName);
  const typeName = element.typeName?.trim() || null;
  return {
    id: element.id ?? `node-${index}`,
    label,
    shortLabel: styled.short,
    detail: typeName,
    icon: styled.icon,
    enabled: element.isEnabled ?? null,
    reserved: Boolean(element.isReserved),
    output: Boolean(element.isOutput),
    routing: isRoutingMarker(element),
  };
}

/** Prefer full chain slots for routing; merge type/enabled from description pass when present. */
export function mergeChainElements(
  elements: ChainElement[] | undefined,
  descriptionElements: ChainElement[] | undefined,
): ChainElement[] {
  const base = elements?.length ? elements : descriptionElements ?? [];
  if (!descriptionElements?.length || !elements?.length) {
    return base;
  }
  const detailById = new Map(
    descriptionElements.filter((item) => item.id).map((item) => [item.id as string, item]),
  );
  return base.map((element) => {
    const detail = element.id ? detailById.get(element.id) : undefined;
    if (!detail) {
      return element;
    }
    return {
      ...element,
      typeName: detail.typeName ?? element.typeName,
      isEnabled: detail.isEnabled ?? element.isEnabled,
      detailBlockID: detail.detailBlockID ?? element.detailBlockID,
      includeInDescription: detail.includeInDescription ?? element.includeInDescription,
    };
  });
}

export function shouldShowChainElement(
  element: ChainElement,
  descriptionIds: Set<string> | null,
): boolean {
  if (element.isReserved) {
    return false;
  }
  if (element.isOutput) {
    return true;
  }
  if (isRoutingMarker(element)) {
    return true;
  }
  if (!descriptionIds) {
    return true;
  }
  return element.id != null && descriptionIds.has(element.id);
}

function pushArrow(layout: ChainLayoutItem[]) {
  if (layout.length > 0 && layout[layout.length - 1]?.kind !== "arrow") {
    layout.push({ kind: "arrow" });
  }
}

function pushNode(layout: ChainLayoutItem[], node: ChainNode) {
  pushArrow(layout);
  layout.push({ kind: "node", node });
}

export function buildChainLayout(elements: ChainElement[]): ChainLayoutItem[] {
  const layout: ChainLayoutItem[] = [];
  let index = 0;

  while (index < elements.length) {
    const element = elements[index];
    const raw = elementRawValue(element);
    const name = element.displayName ?? "";

    if (raw != null && DIVIDER_RAW.has(raw)) {
      const divider = chainNodeFromElement(element, index);
      index += 1;

      const pathA: ChainNode[] = [];
      while (index < elements.length) {
        const slot = elements[index];
        const slotRaw = elementRawValue(slot);
        if (slotRaw != null && (BRANCH_RAW.has(slotRaw) || MIXER_RAW.has(slotRaw) || DIVIDER_RAW.has(slotRaw))) {
          break;
        }
        const node = chainNodeFromElement(slot, index);
        if (!node.reserved && !node.routing) {
          pathA.push(node);
        }
        index += 1;
      }

      if (index < elements.length) {
        const branchRaw = elementRawValue(elements[index]);
        if (branchRaw != null && BRANCH_RAW.has(branchRaw)) {
          index += 1;
        }
      }

      const pathB: ChainNode[] = [];
      while (index < elements.length) {
        const slot = elements[index];
        const slotRaw = elementRawValue(slot);
        if (slotRaw != null && (MIXER_RAW.has(slotRaw) || DIVIDER_RAW.has(slotRaw))) {
          break;
        }
        const node = chainNodeFromElement(slot, index);
        if (!node.reserved && !node.routing) {
          pathB.push(node);
        }
        index += 1;
      }

      let mixer: ChainNode = {
        id: "mixer-placeholder",
        label: "MIXER",
        shortLabel: "Mix",
        detail: null,
        icon: "⊞",
        enabled: null,
        reserved: false,
        output: false,
        routing: true,
      };
      if (index < elements.length) {
        const slotRaw = elementRawValue(elements[index]);
        if (slotRaw != null && MIXER_RAW.has(slotRaw)) {
          mixer = chainNodeFromElement(elements[index], index);
          index += 1;
        }
      }

      pushArrow(layout);
      layout.push({ kind: "split", divider, mixer, pathA, pathB });
      continue;
    }

    if (raw != null && BRANCH_RAW.has(raw)) {
      index += 1;
      continue;
    }

    if (raw != null && MIXER_RAW.has(raw)) {
      const node = chainNodeFromElement(element, index);
      pushNode(layout, node);
      index += 1;
      continue;
    }

    const node = chainNodeFromElement(element, index);
    if (!node.reserved) {
      pushNode(layout, node);
    }
    index += 1;
  }

  return layout;
}

export function chainLayoutFromElements(
  elements: ChainElement[] | undefined,
  options?: {
    descriptionElements?: ChainElement[];
    useDescriptionFilter?: boolean;
    signalOrderElements?: ChainElement[];
  },
): ChainLayoutItem[] {
  const orderSource =
    options?.signalOrderElements?.length ? options.signalOrderElements : elements;
  if (!orderSource?.length && !options?.descriptionElements?.length) {
    return [];
  }
  const merged = mergeChainElements(orderSource, options?.descriptionElements);
  const descriptionIds =
    options?.useDescriptionFilter && options.descriptionElements?.length
      ? new Set(options.descriptionElements.map((item) => item.id).filter(Boolean) as string[])
      : null;

  const filtered = merged.filter((element) => shouldShowChainElement(element, descriptionIds));
  return buildChainLayout(filtered);
}

/** @deprecated Use chainLayoutFromElements */
export function chainNodesFromElements(elements: ChainElement[] | undefined): ChainNode[] {
  return chainLayoutFromElements(elements)
    .filter((item): item is { kind: "node"; node: ChainNode } => item.kind === "node")
    .map((item) => item.node);
}
