"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getOrgStock } from "@/lib/api";

import {
  Button,
  Badge,
  Card,
  MaterialIcon,
  StatCard,
  Input,
  DataTable,
  type DataTableColumn,
  ProgressBar,
} from "@/components/ui-tw";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";

/* ── TODO: replace mock data with real API calls when backend is ready ── */

/* ── types ─────────────────────────────────────────────────────────── */

type StockStatus = "disponivel" | "baixo" | "vencido";

type StockItem = {
  id: number;
  product_name: string;
  product_detail: string;
  batch_code: string;
  quantity: number;
  unit: string;
  expiry_date: string;
  status: StockStatus;
  supplier: string;
};

type DispensationItem = {
  id: number;
  patient_name: string;
  product_name: string;
  quantity: number;
  unit: string;
  date: string;
  prescription_id: string;
  status: "dispensado" | "pendente" | "cancelado";
};

/* ── Data loaded from API ─────────────────────────────────────────── */

/* ── helpers ───────────────────────────────────────────────────────── */

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function fmtDateTime(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })} ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

function daysUntilExpiry(dateStr: string) {
  const now = new Date();
  const exp = new Date(dateStr);
  return Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

const stockStatusConfig: Record<StockStatus, { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }> = {
  disponivel: { tone: "primary", label: "Disponivel" },
  baixo: { tone: "warning", label: "Baixo Estoque" },
  vencido: { tone: "danger", label: "Vencido" },
};

const dispensationStatusConfig: Record<string, { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }> = {
  dispensado: { tone: "success", label: "Dispensado" },
  pendente: { tone: "warning", label: "Pendente" },
  cancelado: { tone: "danger", label: "Cancelado" },
};

const stockIcons: Record<string, string> = {
  "Oleo": "science",
  "Flores": "eco",
  "Capsulas": "medical_services",
  "Tintura": "water_drop",
  "Pomada": "spa",
  "Spray": "vaccines",
};

function getProductIcon(name: string) {
  for (const [key, icon] of Object.entries(stockIcons)) {
    if (name.includes(key)) return icon;
  }
  return "inventory_2";
}

/* ── new stock entry modal ─────────────────────────────────────────── */
function NewStockEntryModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (item: StockItem) => void;
}) {
  const [productName, setProductName] = useState("");
  const [batchCode, setBatchCode] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("unid");
  const [expiryDate, setExpiryDate] = useState("");
  const [supplier, setSupplier] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!productName.trim() || !batchCode.trim() || !quantity || !expiryDate) {
      setFormError("Preencha todos os campos obrigatorios.");
      return;
    }
    // TODO: call real API
    const newItem: StockItem = {
      id: Date.now(),
      product_name: productName.trim(),
      product_detail: "",
      batch_code: batchCode.trim(),
      quantity: parseInt(quantity, 10),
      unit,
      expiry_date: expiryDate,
      status: "disponivel",
      supplier: supplier.trim(),
    };
    onCreated(newItem);
    onClose();
    setProductName("");
    setBatchCode("");
    setQuantity("");
    setExpiryDate("");
    setSupplier("");
    setFormError(null);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-white transition-colors"
        >
          <MaterialIcon icon="close" />
        </button>
        <h3 className="text-xl font-bold font-headline mb-6">
          Registrar Entrada
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nome do Produto"
            icon="inventory_2"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="Ex: Oleo CBD 10%"
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Codigo do Lote"
              icon="qr_code"
              value={batchCode}
              onChange={(e) => setBatchCode(e.target.value)}
              placeholder="#GL-2024-XX"
            />
            <div className="grid grid-cols-2 gap-2">
              <Input
                label="Quantidade"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  Unid
                </label>
                <select
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-3 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                >
                  <option value="unid">unid</option>
                  <option value="g">g</option>
                  <option value="ml">ml</option>
                  <option value="caps">caps</option>
                </select>
              </div>
            </div>
          </div>
          <Input
            label="Data de Validade"
            icon="event"
            type="date"
            value={expiryDate}
            onChange={(e) => setExpiryDate(e.target.value)}
          />
          <Input
            label="Fornecedor"
            icon="local_shipping"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            placeholder="Nome do fornecedor"
          />
          {formError && <p className="text-sm text-error">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" icon="add_circle">
              Registrar
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── new dispensation modal ─────────────────────────────────────────── */
function NewDispensationModal({
  open,
  onClose,
  onCreated,
  stock,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (item: DispensationItem) => void;
  stock: StockItem[];
}) {
  const [patientName, setPatientName] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [prescriptionId, setPrescriptionId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!patientName.trim() || !productId || !quantity || !prescriptionId.trim()) {
      setFormError("Preencha todos os campos obrigatorios.");
      return;
    }
    const product = stock.find((s) => s.id === parseInt(productId, 10));
    // TODO: call real API
    const newItem: DispensationItem = {
      id: Date.now(),
      patient_name: patientName.trim(),
      product_name: product?.product_name ?? "Produto",
      quantity: parseInt(quantity, 10),
      unit: product?.unit ?? "unid",
      date: new Date().toISOString(),
      prescription_id: prescriptionId.trim(),
      status: "dispensado",
    };
    onCreated(newItem);
    onClose();
    setPatientName("");
    setProductId("");
    setQuantity("");
    setPrescriptionId("");
    setFormError(null);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-white transition-colors"
        >
          <MaterialIcon icon="close" />
        </button>
        <h3 className="text-xl font-bold font-headline mb-6">
          Nova Dispensacao
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nome do Paciente"
            icon="person"
            value={patientName}
            onChange={(e) => setPatientName(e.target.value)}
            placeholder="Nome completo"
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Produto
            </label>
            <select
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
            >
              <option value="">Selecionar produto...</option>
              {stock
                .filter((s) => s.status !== "vencido")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.product_name} ({s.batch_code}) - {s.quantity} {s.unit}
                  </option>
                ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Quantidade"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="0"
            />
            <Input
              label="ID da Receita"
              icon="receipt"
              value={prescriptionId}
              onChange={(e) => setPrescriptionId(e.target.value)}
              placeholder="RX-2024-XXXX"
            />
          </div>
          {formError && <p className="text-sm text-error">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" icon="add_circle">
              Dispensar
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── page ───────────────────────────────────────────────────────────── */
export default function EstoquePage() {
  const router = useRouter();
  const session = useApiSession();
  const [activeTab, setActiveTab] = useState<"estoque" | "dispensacao">("estoque");
  const [stock, setStock] = useState<StockItem[]>([]);
  const [dispensations, setDispensations] = useState<DispensationItem[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [showStockModal, setShowStockModal] = useState(false);
  const [showDispensationModal, setShowDispensationModal] = useState(false);
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchStock() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await getOrgStock();
        if (cancelled) return;
        const d = res.data as Record<string, unknown>;
        setStock((d.stock as StockItem[]) ?? []);
        setDispensations((d.dispensations as DispensationItem[]) ?? []);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar o estoque.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchStock();
    return () => { cancelled = true; };
  }, []);

  /* stats */
  const totalProducts = stock.length;
  const expiringBatches = stock.filter((s) => {
    const days = daysUntilExpiry(s.expiry_date);
    return days > 0 && days <= 90;
  }).length;
  const dispensationsThisMonth = dispensations.filter((d) => {
    const now = new Date();
    const date = new Date(d.date);
    return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
  }).length;
  const stockValue = "R$ 84k"; // TODO: calculate from real data

  /* alerts */
  const expiringSoon = stock.filter((s) => {
    const days = daysUntilExpiry(s.expiry_date);
    return days > 0 && days <= 90;
  });
  const lowStock = stock.filter((s) => s.status === "baixo");
  const expired = stock.filter((s) => s.status === "vencido");

  /* filtered stock */
  const filteredStock = stock.filter((s) =>
    searchTerm
      ? s.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.batch_code.toLowerCase().includes(searchTerm.toLowerCase())
      : true,
  );

  /* filtered dispensations */
  const filteredDispensations = dispensations.filter((d) =>
    searchTerm
      ? d.patient_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        d.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        d.prescription_id.toLowerCase().includes(searchTerm.toLowerCase())
      : true,
  );

  /* stock table columns */
  const stockColumns: DataTableColumn[] = [
    {
      key: "product_name",
      label: "Produto",
      sortable: true,
      render: (_val, row) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary-container/20 flex items-center justify-center shrink-0">
            <MaterialIcon
              icon={getProductIcon(row.product_name as string)}
              filled
              className="text-primary"
            />
          </div>
          <div>
            <p className="font-bold text-sm font-headline">{row.product_name as string}</p>
            <p className="text-[10px] text-stone-500 uppercase">
              {row.product_detail as string}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "batch_code",
      label: "Lote",
      sortable: true,
      render: (val) => (
        <span className="text-xs font-mono text-stone-300">{val as string}</span>
      ),
    },
    {
      key: "quantity",
      label: "Qtd / Unidade",
      sortable: true,
      render: (_val, row) => (
        <span className="text-xs font-bold">
          {row.quantity as number}{" "}
          <span className="text-stone-500 font-normal">{row.unit as string}</span>
        </span>
      ),
    },
    {
      key: "expiry_date",
      label: "Validade",
      sortable: true,
      render: (val) => {
        const days = daysUntilExpiry(val as string);
        return (
          <span
            className={cn(
              "text-xs",
              days <= 0 ? "text-error font-semibold" : days <= 90 ? "text-amber-400" : "text-stone-300",
            )}
          >
            {fmtDate(val as string)}
          </span>
        );
      },
    },
    {
      key: "status",
      label: "Status",
      render: (val) => {
        const cfg = stockStatusConfig[val as StockStatus];
        return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
      },
    },
    {
      key: "supplier",
      label: "Fornecedor",
      render: (val) => (
        <span className="text-xs text-stone-400">{val as string}</span>
      ),
    },
  ];

  if (session.loading || apiLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-stone-500 text-sm font-medium">Carregando estoque...</p>
        </div>
      </div>
    );
  }

  if (apiError && stock.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
          <p className="text-on-surface-variant text-sm">{apiError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-white mb-2">
            Gestao de Estoque
          </h1>
          <p className="text-on-surface-variant max-w-xl text-sm">
            Controle e rastreabilidade. Gerencie produtos, lotes, dispensacoes e
            conformidade sanitaria.
          </p>
        </div>
        <div className="flex gap-3">
          <Button
            icon="add_circle"
            onClick={() => setShowStockModal(true)}
            className="rounded-full shadow-lg shadow-primary/20"
          >
            Registrar Entrada
          </Button>
          <Button
            icon="outbound"
            variant="secondary"
            onClick={() => setShowDispensationModal(true)}
            className="rounded-full"
          >
            Nova Dispensacao
          </Button>
        </div>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="inventory_2"
          label="Produtos em Estoque"
          value={totalProducts}
        />
        <StatCard
          icon="alarm_on"
          label="Lotes Prox. Vencimento"
          value={expiringBatches}
          delta={expiringBatches > 0 ? "Requer atencao" : undefined}
          deltaType="down"
        />
        <StatCard
          icon="outbound"
          label="Dispensacoes / Mes"
          value={dispensationsThisMonth}
          delta="+8% este mes"
          deltaType="up"
        />
        <StatCard
          icon="payments"
          label="Valor em Estoque"
          value={stockValue}
        />
      </div>

      {/* alerts */}
      {(expired.length > 0 || lowStock.length > 0 || expiringSoon.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {expired.length > 0 && (
            <Card className="border-l-4 border-l-error">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-error/20 flex items-center justify-center shrink-0">
                  <MaterialIcon icon="dangerous" className="text-error" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-error">
                    {expired.length} Produto{expired.length > 1 ? "s" : ""} Vencido{expired.length > 1 ? "s" : ""}
                  </h4>
                  <p className="text-[10px] text-stone-500">
                    {expired.map((s) => s.product_name).join(", ")}
                  </p>
                </div>
              </div>
            </Card>
          )}
          {lowStock.length > 0 && (
            <Card className="border-l-4 border-l-amber-500">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center shrink-0">
                  <MaterialIcon icon="warning" className="text-amber-400" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-amber-400">
                    {lowStock.length} Estoque Baixo
                  </h4>
                  <p className="text-[10px] text-stone-500">
                    {lowStock.map((s) => s.product_name).join(", ")}
                  </p>
                </div>
              </div>
            </Card>
          )}
          {expiringSoon.length > 0 && (
            <Card className="border-l-4 border-l-amber-600">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-600/20 flex items-center justify-center shrink-0">
                  <MaterialIcon icon="schedule" className="text-amber-500" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-amber-500">
                    {expiringSoon.length} Proximo{expiringSoon.length > 1 ? "s" : ""} do Vencimento
                  </h4>
                  <p className="text-[10px] text-stone-500">
                    Dentro de 90 dias
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* tabs + search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex gap-1 glass-panel rounded-lg p-1">
          {(["estoque", "dispensacao"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-6 py-2.5 rounded-md text-sm font-bold font-headline uppercase tracking-widest transition-colors",
                activeTab === tab
                  ? "bg-primary/10 text-primary"
                  : "text-stone-400 hover:text-stone-200 hover:bg-white/5",
              )}
            >
              {tab === "estoque" ? "Estoque" : "Dispensacao"}
            </button>
          ))}
        </div>
        <div className="w-full sm:w-72">
          <Input
            icon="search"
            placeholder={
              activeTab === "estoque"
                ? "Filtrar por produto ou lote..."
                : "Filtrar por paciente ou produto..."
            }
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* tab content: stock table */}
      {activeTab === "estoque" && (
        <>
          {/* desktop table */}
          <div className="hidden md:block">
            <DataTable
              columns={stockColumns}
              data={filteredStock.map((s) => ({ ...s }))}
              emptyMessage="Nenhum produto encontrado."
            />
          </div>

          {/* mobile cards */}
          <div className="md:hidden space-y-3">
            {filteredStock.map((item) => {
              const cfg = stockStatusConfig[item.status];
              return (
                <Card
                  key={item.id}
                  padding="sm"
                  className={cn(
                    "flex items-center gap-4",
                    item.status === "vencido" && "border-l-4 border-l-error",
                    item.status === "baixo" && "border-l-4 border-l-amber-500",
                  )}
                >
                  <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center border border-white/5 shrink-0">
                    <MaterialIcon
                      icon={getProductIcon(item.product_name)}
                      filled
                      className="text-primary"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-sm text-on-surface truncate">
                      {item.product_name}
                    </h4>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-on-surface-variant">
                        {item.quantity} {item.unit}
                      </span>
                      <span className="w-1 h-1 bg-white/20 rounded-full" />
                      <Badge tone={cfg.tone}>{cfg.label}</Badge>
                    </div>
                    <p className="text-[10px] text-stone-500 mt-1">
                      Lote: {item.batch_code} | Val: {fmtDate(item.expiry_date)}
                    </p>
                  </div>
                  <button className="p-2 rounded-full bg-surface-container-highest flex items-center justify-center text-on-surface-variant shrink-0">
                    <MaterialIcon icon="more_vert" size="sm" />
                  </button>
                </Card>
              );
            })}
            {filteredStock.length === 0 && (
              <Card className="text-center py-8">
                <p className="text-stone-500 text-sm">
                  Nenhum produto encontrado.
                </p>
              </Card>
            )}
          </div>
        </>
      )}

      {/* tab content: dispensations */}
      {activeTab === "dispensacao" && (
        <>
          {/* desktop table */}
          <Card padding="sm" className="hidden md:block overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/5">
                    {["Paciente", "Produto", "Qtd", "Receita", "Data", "Status"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredDispensations.map((d) => {
                    const cfg = dispensationStatusConfig[d.status];
                    return (
                      <tr
                        key={d.id}
                        className="hover:bg-white/5 transition-colors"
                      >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-secondary-container/30 flex items-center justify-center text-secondary shrink-0">
                              <MaterialIcon icon="person" size="sm" />
                            </div>
                            <span className="text-sm font-bold text-stone-200">
                              {d.patient_name}
                            </span>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-sm text-stone-300">
                          {d.product_name}
                        </td>
                        <td className="px-5 py-4 text-sm font-bold">
                          {d.quantity}{" "}
                          <span className="text-stone-500 font-normal">
                            {d.unit}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-xs font-mono text-stone-400">
                          {d.prescription_id}
                        </td>
                        <td className="px-5 py-4 text-xs text-stone-400">
                          {fmtDateTime(d.date)}
                        </td>
                        <td className="px-5 py-4">
                          <Badge tone={cfg.tone}>{cfg.label}</Badge>
                        </td>
                      </tr>
                    );
                  })}
                  {filteredDispensations.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-5 py-10 text-center text-sm text-stone-500"
                      >
                        Nenhuma dispensacao encontrada.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* mobile cards */}
          <div className="md:hidden space-y-3">
            {filteredDispensations.map((d) => {
              const cfg = dispensationStatusConfig[d.status];
              return (
                <Card key={d.id} padding="sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-secondary-container/30 flex items-center justify-center text-secondary shrink-0">
                        <MaterialIcon icon="person" size="sm" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-on-surface">
                          {d.patient_name}
                        </p>
                        <p className="text-[10px] text-on-surface-variant">
                          {d.product_name}
                        </p>
                      </div>
                    </div>
                    <Badge tone={cfg.tone}>{cfg.label}</Badge>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-stone-500 pt-2 border-t border-white/5">
                    <span>
                      {d.quantity} {d.unit} | {d.prescription_id}
                    </span>
                    <span>{fmtDateTime(d.date)}</span>
                  </div>
                </Card>
              );
            })}
            {filteredDispensations.length === 0 && (
              <Card className="text-center py-8">
                <p className="text-stone-500 text-sm">
                  Nenhuma dispensacao encontrada.
                </p>
              </Card>
            )}
          </div>
        </>
      )}

      {/* bottom section: last dispensations + traceability */}
      {activeTab === "estoque" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* recent dispensations */}
          <Card className="lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h4 className="font-bold text-lg font-headline flex items-center gap-2">
                <MaterialIcon icon="history" className="text-primary" />
                Ultimas Saidas / Dispensacoes
              </h4>
              <button
                onClick={() => setActiveTab("dispensacao")}
                className="text-xs text-primary font-bold hover:underline"
              >
                Ver Historico Completo
              </button>
            </div>
            <div className="space-y-3">
              {dispensations.slice(0, 3).map((d) => (
                <div
                  key={d.id}
                  className="flex items-center gap-4 p-4 rounded-xl bg-stone-900/50 border border-stone-800/50"
                >
                  <div className="w-8 h-8 rounded-full bg-secondary-container/30 flex items-center justify-center text-secondary shrink-0">
                    <MaterialIcon icon="outbound" size="sm" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-bold">
                      {d.quantity}x {d.product_name}
                    </p>
                    <p className="text-[10px] text-stone-500 uppercase tracking-tight">
                      Paciente: {d.patient_name} | {fmtDateTime(d.date)}
                    </p>
                  </div>
                  <MaterialIcon
                    icon="receipt_long"
                    className="text-stone-500 cursor-pointer hover:text-stone-200 transition-colors"
                    size="sm"
                  />
                </div>
              ))}
            </div>
          </Card>

          {/* traceability report */}
          <Card className="flex flex-col justify-between">
            <div>
              <h4 className="font-bold text-lg font-headline mb-2">
                Relatorio de Rastreabilidade
              </h4>
              <p className="text-xs text-stone-400 mb-6 leading-relaxed">
                Gere um log completo de toda a movimentacao de um lote especifico
                para fins de auditoria sanitaria.
              </p>
              <div className="space-y-3">
                <div className="flex flex-col gap-1.5">
                  <select className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-2.5 text-xs text-stone-200 outline-none focus:border-primary-container transition-colors">
                    <option>Selecionar Lote...</option>
                    {stock.map((s) => (
                      <option key={s.id} value={s.batch_code}>
                        {s.batch_code} - {s.product_name}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  variant="ghost"
                  icon="download"
                  className="w-full bg-stone-800 hover:bg-stone-700 text-on-surface"
                  size="sm"
                >
                  Exportar PDF Auditavel
                </Button>
              </div>
            </div>
            <div className="mt-8 pt-6 border-t border-stone-800/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <MaterialIcon
                    icon="verified_user"
                    className="text-primary"
                  />
                </div>
                <div>
                  <p className="text-[10px] uppercase font-black text-primary">
                    Conformidade Sanitaria
                  </p>
                  <p className="text-[11px] text-stone-400 leading-tight">
                    Sistema operando sob diretrizes da RDC 327/2019.
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* modals */}
      <NewStockEntryModal
        open={showStockModal}
        onClose={() => setShowStockModal(false)}
        onCreated={(item) => setStock((prev) => [item, ...prev])}
      />
      <NewDispensationModal
        open={showDispensationModal}
        onClose={() => setShowDispensationModal(false)}
        onCreated={(item) => setDispensations((prev) => [item, ...prev])}
        stock={stock}
      />
    </div>
  );
}
