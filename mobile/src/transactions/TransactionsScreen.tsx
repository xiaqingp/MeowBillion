import DateTimePicker from "@react-native-community/datetimepicker";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  CalendarDays,
  ChevronRight,
  Plus,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  buildTransactionQuery,
  buildTransactionReviewPayload,
  TransactionFilters,
} from "./api";
import { formatDate, monthBounds, parseDate } from "./dateFilters";

type Api = {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
};
export type Transaction = {
  TransactionID: string;
  Date: string;
  Merchant: string;
  Amount: number;
  Direction: string;
  AccountName: string;
  Type?: string;
  IsB?: string;
  Ratio?: number;
  Mown?: number;
  Note?: string;
  SubType?: string;
  Pending?: number;
  Reviewed?: number;
  ImportedFromLegacy?: number;
  TripID?: string;
  RentalPropertyID?: string;
};
type Options = {
  min_date?: string;
  max_date?: string;
  accounts: Array<{ account_id: string; account_name: string }>;
  statuses: Array<{ value: string; label: string; count: number }>;
  trips: Array<{ id: string; label: string }>;
  rental_properties: Array<{ id: string; label: string }>;
};
type CategoryOptions = {
  categories: string[];
  subcategories: Record<string, string[]>;
};
type Props = {
  api: Api;
  formatMoney(value: number): string;
  errorMessage(error: unknown): string;
};

export function TransactionsScreen({ api, formatMoney, errorMessage }: Props) {
  const [filters, setFilters] = useState<TransactionFilters>({
    page: 1,
    limit: 50,
    reviewedFilter: "unreviewed",
  });
  const [data, setData] = useState<{
    transactions: Transaction[];
    total_count: number;
    total_pages: number;
  }>();
  const [options, setOptions] = useState<Options>();
  const [categories, setCategories] = useState<string[]>([]);
  const [subcategories, setSubcategories] = useState<Record<string, string[]>>(
    {},
  );
  const [selected, setSelected] = useState<Transaction>();
  const [createOpen, setCreateOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.get(buildTransactionQuery(filters)));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [api, errorMessage, filters]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    Promise.all([
      api.get<Options>("/api/transaction_filter_options"),
      api.get<CategoryOptions>("/api/category_options"),
    ])
      .then(([nextOptions, categoryOptions]) => {
        setOptions(nextOptions);
        setCategories(categoryOptions.categories);
        setSubcategories(categoryOptions.subcategories);
      })
      .catch(() => undefined);
  }, [api]);

  function patchFilters(patch: Partial<TransactionFilters>) {
    setFilters((current) => ({ ...current, page: 1, ...patch }));
  }

  return (
    <View style={s.screen}>
      <View style={s.header}>
        <View>
          <Text style={s.title}>Transactions</Text>
          <Text style={s.muted}>{data?.total_count || 0} total</Text>
        </View>
        <View style={s.actions}>
          <IconButton onPress={() => setFilterOpen(true)}>
            <SlidersHorizontal color="#4d53b7" size={20} />
          </IconButton>
          <IconButton onPress={() => setCreateOpen(true)}>
            <Plus color="#4d53b7" size={21} />
          </IconButton>
        </View>
      </View>
      <View style={s.searchField}>
        <Search color="#7a8499" size={18} />
        <TextInput
          autoCapitalize="none"
          onChangeText={(query) => patchFilters({ query })}
          placeholder="Search merchant, category, note..."
          placeholderTextColor="#8992a4"
          style={s.searchInput}
          value={filters.query || ""}
        />
      </View>
      <View style={s.statusChips}>
        {[
          ["unreviewed", "Needs review"],
          ["reviewed", "Reviewed"],
          ["pending", "Pending"],
          ["all", "All"],
        ].map(([value, label]) => (
          <Chip
            active={filters.reviewedFilter === value}
            key={value}
            label={label}
            onPress={() => patchFilters({ reviewedFilter: value })}
          />
        ))}
      </View>
      {error ? (
        <Pressable onPress={load} style={s.error}>
          <Text style={s.errorText}>{error} Tap to retry.</Text>
        </Pressable>
      ) : null}
      {loading && !data ? (
        <ActivityIndicator color="#6268dc" style={s.loader} />
      ) : (
        <FlatList
          contentContainerStyle={s.list}
          data={data?.transactions || []}
          keyExtractor={(item) => item.TransactionID}
          ListEmptyComponent={
            <Text style={s.empty}>No transactions match these filters.</Text>
          }
          renderItem={({ item }) => (
            <Pressable onPress={() => setSelected(item)} style={s.row}>
              <View style={s.rowBody}>
                <Text numberOfLines={1} style={s.merchant}>
                  {item.Merchant || "Transaction"}
                </Text>
                <Text style={s.meta}>
                  {item.Date} / {item.AccountName}
                </Text>
                <Text style={s.meta}>
                  {item.Pending
                    ? "Pending"
                    : [item.Type || "Uncategorized", item.SubType]
                        .filter(Boolean)
                        .join(" / ")}
                </Text>
              </View>
              <Text
                style={[
                  s.amount,
                  item.Direction === "inflow" ? s.inflow : s.outflow,
                ]}
              >
                {item.Direction === "inflow" ? "+" : "-"}
                {formatMoney(Math.abs(Number(item.Amount || 0)))}
              </Text>
            </Pressable>
          )}
        />
      )}
      <View style={s.pagination}>
        <Button
          disabled={(filters.page || 1) <= 1 || loading}
          label="Previous"
          onPress={() =>
            setFilters((current) => ({
              ...current,
              page: (current.page || 1) - 1,
            }))
          }
        />
        <Text style={s.meta}>
          Page {filters.page} of {data?.total_pages || 1}
        </Text>
        <Button
          disabled={loading || (filters.page || 1) >= (data?.total_pages || 1)}
          label="Next"
          onPress={() =>
            setFilters((current) => ({
              ...current,
              page: (current.page || 1) + 1,
            }))
          }
        />
      </View>
      <FilterModal
        categories={categories}
        subcategories={subcategories}
        filters={filters}
        onApply={patchFilters}
        onClose={() => setFilterOpen(false)}
        open={filterOpen}
        options={options}
      />
      <EditorModal
        api={api}
        categories={categories}
        subcategories={subcategories}
        errorMessage={errorMessage}
        onClose={() => setSelected(undefined)}
        onSaved={async () => {
          setSelected(undefined);
          await load();
        }}
        options={options}
        transaction={selected}
      />
      <CreateModal
        api={api}
        categories={categories}
        subcategories={subcategories}
        errorMessage={errorMessage}
        onClose={() => setCreateOpen(false)}
        onSaved={async () => {
          setCreateOpen(false);
          await load();
        }}
        open={createOpen}
      />
    </View>
  );
}

function EditorModal({
  api,
  categories,
  subcategories,
  transaction,
  options,
  onClose,
  onSaved,
  errorMessage,
}: {
  api: Api;
  categories: string[];
  subcategories: Record<string, string[]>;
  transaction?: Transaction;
  options?: Options;
  onClose(): void;
  onSaved(): Promise<void>;
  errorMessage(error: unknown): string;
}) {
  const [type, setType] = useState("Other");
  const [note, setNote] = useState("");
  const [subtype, setSubtype] = useState("");
  const [tripId, setTripId] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [candidates, setCandidates] = useState<
    Array<{
      transaction_id: string;
      merchant: string;
      date: string;
      amount: number;
    }>
  >([]);

  useEffect(() => {
    if (!transaction) return;
    setType(transaction.Type || "Other");
    setNote(transaction.Note || "");
    setSubtype(transaction.SubType || "");
    setTripId(transaction.TripID || "");
    setPropertyId(transaction.RentalPropertyID || "");
    setDeleteArmed(false);
    setCandidates([]);
    setError("");
  }, [transaction]);
  if (!transaction) return null;

  const readOnly = Boolean(transaction.Pending || transaction.Reviewed);
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      await onSaved();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <View style={s.scrim}>
        <SafeAreaView edges={["top", "bottom"]} style={s.modalSafe}>
          <ScrollView contentContainerStyle={s.modal}>
            <ModalHeader
              onClose={onClose}
              title={transaction.Merchant || "Transaction"}
            />
            <Text style={s.meta}>
              {transaction.Date} / {transaction.AccountName}
            </Text>
            <Text style={s.modalAmount}>
              {transaction.Direction === "inflow" ? "+" : "-"}$
              {Math.abs(transaction.Amount).toFixed(2)}
            </Text>
            {transaction.Pending ? (
              <Text style={s.warning}>
                Pending transactions cannot be changed until posted.
              </Text>
            ) : (
              <>
                <Label text="Category" />
                <TextInput
                  editable={!readOnly}
                  onChangeText={(nextType) => {
                    setType(nextType);
                    setSubtype("");
                  }}
                  style={[s.input, readOnly && s.readOnlyInput]}
                  value={type}
                />
                <View style={s.categoryGrid}>
                  {categories.map((category) => (
                    <Chip
                      active={type === category}
                      disabled={readOnly}
                      key={category}
                      label={category}
                      onPress={() => {
                        setType(category);
                        setSubtype("");
                      }}
                    />
                  ))}
                </View>
                <Label text="Subcategory" />
                <View style={s.categoryGrid}>
                  <Chip
                    active={!subtype}
                    disabled={readOnly}
                    label="No subcategory"
                    onPress={() => setSubtype("")}
                  />
                  {[
                    ...new Set([
                      ...(subcategories[type] || []),
                      ...(subtype ? [subtype] : []),
                    ]),
                  ].map((item) => (
                    <Chip
                      active={subtype === item}
                      disabled={readOnly}
                      key={item}
                      label={item}
                      onPress={() => setSubtype(item)}
                    />
                  ))}
                </View>
                {type.toLowerCase() === "travel" ? (
                  <>
                    <Label text="Trip" />
                    <View style={s.categoryGrid}>
                      {options?.trips.map((trip) => (
                        <Chip
                          active={tripId === trip.id}
                          disabled={readOnly}
                          key={trip.id}
                          label={trip.label}
                          onPress={() =>
                            setTripId(tripId === trip.id ? "" : trip.id)
                          }
                        />
                      ))}
                    </View>
                  </>
                ) : null}
                {type.toLowerCase() === "rentals" ? (
                  <>
                    <Label text="Property" />
                    <View style={s.categoryGrid}>
                      {options?.rental_properties.map((property) => (
                        <Chip
                          active={propertyId === property.id}
                          disabled={readOnly}
                          key={property.id}
                          label={property.label}
                          onPress={() =>
                            setPropertyId(
                              propertyId === property.id ? "" : property.id,
                            )
                          }
                        />
                      ))}
                    </View>
                  </>
                ) : null}
                <Label text="Note" />
                <TextInput
                  editable={!readOnly}
                  multiline
                  onChangeText={setNote}
                  style={[s.input, s.note, readOnly && s.readOnlyInput]}
                  value={note}
                />
                {error ? <Text style={s.errorText}>{error}</Text> : null}
                {!transaction.Reviewed ? (
                  <Button
                    disabled={busy}
                    label={busy ? "Reviewing" : "Review"}
                    onPress={() =>
                      run(() =>
                        api.post("/api/update_transaction", {
                          ...buildTransactionReviewPayload(transaction),
                          type,
                          note,
                          subtype,
                          trip_id: tripId,
                          rental_property_id: propertyId,
                        }),
                      )
                    }
                  />
                ) : (
                  <Button
                    disabled={busy}
                    label={busy ? "Updating" : "Reviewed"}
                    onPress={() =>
                      run(() =>
                        api.post("/api/unconfirm_transaction", {
                          transaction_id: transaction.TransactionID,
                        }),
                      )
                    }
                  />
                )}
                {transaction.AccountName === "Legacy" && !readOnly ? (
                  <Button
                    disabled={busy}
                    label="Find merge candidates"
                    onPress={async () => {
                      try {
                        setCandidates(
                          await api.get(
                            `/api/merge_candidates?legacy_id=${encodeURIComponent(transaction.TransactionID)}`,
                          ),
                        );
                      } catch (requestError) {
                        setError(errorMessage(requestError));
                      }
                    }}
                  />
                ) : null}
                {candidates.map((candidate) => (
                  <Pressable
                    key={candidate.transaction_id}
                    onPress={() =>
                      run(() =>
                        api.post("/api/merge_transactions", {
                          legacy_id: transaction.TransactionID,
                          plaid_id: candidate.transaction_id,
                        }),
                      )
                    }
                    style={s.candidate}
                  >
                    <Text style={s.merchant}>{candidate.merchant}</Text>
                    <Text style={s.meta}>
                      {candidate.date} / ${candidate.amount}
                    </Text>
                  </Pressable>
                ))}
                {!readOnly ? (
                  <Button
                    danger
                    disabled={busy}
                    label={
                      deleteArmed ? "Confirm delete" : "Delete transaction"
                    }
                    onPress={() =>
                      deleteArmed
                        ? run(() =>
                            api.post("/api/delete_transaction", {
                              transaction_id: transaction.TransactionID,
                            }),
                          )
                        : setDeleteArmed(true)
                    }
                  />
                ) : null}
              </>
            )}
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

function CreateModal({
  api,
  categories,
  subcategories,
  open,
  onClose,
  onSaved,
  errorMessage,
}: {
  api: Api;
  categories: string[];
  subcategories: Record<string, string[]>;
  open: boolean;
  onClose(): void;
  onSaved(): Promise<void>;
  errorMessage(error: unknown): string;
}) {
  const [date, setDate] = useState(new Date());
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("Other");
  const [subtype, setSubtype] = useState("");
  const [direction, setDirection] = useState("outflow");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setError("");
    try {
      if (!merchant.trim() || !Number(amount))
        throw new Error("Merchant and a non-zero amount are required.");
      await api.post("/api/create_manual_transaction", {
        date: formatDate(date),
        merchant,
        amount: Number(amount),
        type,
        subtype,
        direction,
        reviewed: 1,
      });
      await onSaved();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      animationType="slide"
      onRequestClose={onClose}
      transparent
      visible={open}
    >
      <View style={s.scrim}>
        <SafeAreaView edges={["top", "bottom"]} style={s.modalSafe}>
          <ScrollView contentContainerStyle={s.modal}>
            <ModalHeader onClose={onClose} title="Add transaction" />
            <DateField label="Date" onChange={setDate} value={date} />
            <Label text="Merchant" />
            <TextInput
              onChangeText={setMerchant}
              style={s.input}
              value={merchant}
            />
            <Label text="Amount" />
            <TextInput
              keyboardType="decimal-pad"
              onChangeText={setAmount}
              style={s.input}
              value={amount}
            />
            <Label text="Direction" />
            <View style={s.inlineChips}>
              <Chip
                active={direction === "outflow"}
                label="Outflow"
                onPress={() => setDirection("outflow")}
              />
              <Chip
                active={direction === "inflow"}
                label="Inflow"
                onPress={() => setDirection("inflow")}
              />
            </View>
            <Label text="Category" />
            <TextInput
              onChangeText={(nextType) => {
                setType(nextType);
                setSubtype("");
              }}
              style={s.input}
              value={type}
            />
            <View style={s.categoryGrid}>
              {categories.map((category) => (
                <Chip
                  active={type === category}
                  key={category}
                  label={category}
                  onPress={() => {
                    setType(category);
                    setSubtype("");
                  }}
                />
              ))}
            </View>
            <Label text="Subcategory" />
            <View style={s.categoryGrid}>
              <Chip
                active={!subtype}
                label="No subcategory"
                onPress={() => setSubtype("")}
              />
              {[...new Set(subcategories[type] || [])].map((item) => (
                <Chip
                  active={subtype === item}
                  key={item}
                  label={item}
                  onPress={() => setSubtype(item)}
                />
              ))}
            </View>
            {error ? <Text style={s.errorText}>{error}</Text> : null}
            <Button
              disabled={busy}
              label={busy ? "Saving" : "Create transaction"}
              onPress={save}
            />
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

type PickerKind = "account" | "category" | "subcategory" | "assignment";

function FilterModal({
  open,
  onClose,
  filters,
  onApply,
  options,
  categories,
  subcategories,
}: {
  open: boolean;
  onClose(): void;
  filters: TransactionFilters;
  onApply(patch: Partial<TransactionFilters>): void;
  options?: Options;
  categories: string[];
  subcategories: Record<string, string[]>;
}) {
  const [draft, setDraft] = useState(filters);
  const [picker, setPicker] = useState<PickerKind>();
  useEffect(() => {
    if (open) setDraft(filters);
  }, [filters, open]);
  const accountLabel =
    options?.accounts.find((account) => account.account_id === draft.account)
      ?.account_name || "All accounts";
  const categoryLabel =
    draft.category && draft.category !== "all"
      ? draft.category
      : "All categories";
  const subcategoryLabel =
    draft.subtype && draft.subtype !== "all"
      ? draft.subtype
      : "All subcategories";
  const assignmentLabel = assignmentSummary(draft.assignment, options);
  const reset = () =>
    setDraft((current) => ({
      ...current,
      account: "all",
      category: "all",
      subtype: "all",
      assignment: "all",
      direction: "all",
      startDate: "",
      endDate: "",
    }));
  const apply = () => {
    onApply(draft);
    onClose();
  };

  return (
    <>
      <Modal
        animationType="slide"
        onRequestClose={onClose}
        transparent
        visible={open}
      >
        <View style={s.scrim}>
          <SafeAreaView edges={["top", "bottom"]} style={s.modalSafe}>
            <View style={s.filterSheet}>
              <ModalHeader onClose={onClose} title="Filters" />
              <ScrollView
                contentContainerStyle={s.filterBody}
                style={s.filterScroll}
              >
                <FilterRow
                  label="Account"
                  onPress={() => setPicker("account")}
                  value={accountLabel}
                />
                <FilterRow
                  label="Category"
                  onPress={() => setPicker("category")}
                  value={categoryLabel}
                />
                <FilterRow
                  disabled={draft.category === "all"}
                  label="Subcategory"
                  onPress={() => setPicker("subcategory")}
                  value={
                    draft.category === "all"
                      ? "Select a category first"
                      : subcategoryLabel
                  }
                />
                <FilterRow
                  label="Assignment"
                  onPress={() => setPicker("assignment")}
                  value={assignmentLabel}
                />
                <Label text="Direction" />
                <View style={s.inlineChips}>
                  {["all", "outflow", "inflow"].map((value) => (
                    <Chip
                      active={(draft.direction || "all") === value}
                      key={value}
                      label={value}
                      onPress={() =>
                        setDraft((current) => ({
                          ...current,
                          direction: value,
                        }))
                      }
                    />
                  ))}
                </View>
                <Label text="Date range" />
                <DateField
                  label="Month"
                  month
                  onChange={(date) =>
                    setDraft((current) => ({
                      ...current,
                      ...monthBounds(date),
                    }))
                  }
                  value={parseDate(draft.startDate)}
                />
                <DateField
                  label="Start date"
                  onChange={(date) =>
                    setDraft((current) => ({
                      ...current,
                      startDate: formatDate(date),
                    }))
                  }
                  value={parseDate(draft.startDate)}
                />
                <DateField
                  label="End date"
                  onChange={(date) =>
                    setDraft((current) => ({
                      ...current,
                      endDate: formatDate(date),
                    }))
                  }
                  value={parseDate(draft.endDate)}
                />
                <Pressable
                  onPress={() =>
                    setDraft((current) => ({
                      ...current,
                      startDate: "",
                      endDate: "",
                    }))
                  }
                  style={s.clearDates}
                >
                  <Text style={s.clearDatesText}>Clear dates</Text>
                </Pressable>
              </ScrollView>
              <View style={s.filterFooter}>
                <Pressable onPress={reset} style={s.resetButton}>
                  <Text style={s.resetButtonText}>Reset</Text>
                </Pressable>
                <Pressable onPress={apply} style={s.applyButton}>
                  <Text style={s.buttonText}>Apply filters</Text>
                </Pressable>
              </View>
            </View>
          </SafeAreaView>
        </View>
      </Modal>
      <FilterPickerModal
        categories={categories}
        subcategories={subcategories}
        selectedCategory={draft.category}
        kind={picker}
        onChoose={(value) => {
          setDraft((current) =>
            picker === "account"
              ? { ...current, account: value }
              : picker === "category"
                ? { ...current, category: value, subtype: "all" }
                : picker === "subcategory"
                  ? { ...current, subtype: value }
                  : { ...current, assignment: value },
          );
          setPicker(undefined);
        }}
        onClose={() => setPicker(undefined)}
        options={options}
      />
    </>
  );
}

function FilterPickerModal({
  kind,
  options,
  categories,
  subcategories,
  selectedCategory,
  onChoose,
  onClose,
}: {
  kind?: PickerKind;
  options?: Options;
  categories: string[];
  subcategories: Record<string, string[]>;
  selectedCategory: string | undefined;
  onChoose(value: string): void;
  onClose(): void;
}) {
  const [query, setQuery] = useState("");
  const [assignmentTab, setAssignmentTab] = useState<"trip" | "property">(
    "trip",
  );
  useEffect(() => {
    setQuery("");
  }, [kind]);
  if (!kind) return null;
  const title =
    kind === "account"
      ? "Select account"
      : kind === "category"
        ? "Select category"
        : kind === "subcategory"
          ? "Select subcategory"
          : "Select assignment";
  const source =
    kind === "account"
      ? (options?.accounts || []).map((account) => ({
          id: account.account_id,
          label: account.account_name,
        }))
      : kind === "category"
        ? categories.map((category) => ({ id: category, label: category }))
        : kind === "subcategory"
          ? (subcategories[selectedCategory || ""] || []).map(
              (subcategory) => ({
                id: subcategory,
                label: subcategory,
              }),
            )
          : assignmentTab === "trip"
            ? (options?.trips || []).map((trip) => ({
                id: `trip:${trip.id}`,
                label: trip.label,
              }))
            : (options?.rental_properties || []).map((property) => ({
                id: `property:${property.id}`,
                label: property.label,
              }));
  const visibleItems = source.filter((item) =>
    item.label.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const allLabel =
    kind === "account"
      ? "All accounts"
      : kind === "category"
        ? "All categories"
        : kind === "subcategory"
          ? "All subcategories"
          : "All assignments";
  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <View style={s.scrim}>
        <SafeAreaView edges={["top", "bottom"]} style={s.modalSafe}>
          <View style={s.pickerSheet}>
            <ModalHeader onClose={onClose} title={title} />
            {kind === "assignment" ? (
              <View style={s.assignmentTabs}>
                <Chip
                  active={assignmentTab === "trip"}
                  label="Trips"
                  onPress={() => setAssignmentTab("trip")}
                />
                <Chip
                  active={assignmentTab === "property"}
                  label="Rental properties"
                  onPress={() => setAssignmentTab("property")}
                />
              </View>
            ) : null}
            <View style={s.searchField}>
              <Search color="#7a8499" size={18} />
              <TextInput
                autoCapitalize="none"
                onChangeText={setQuery}
                placeholder="Search options..."
                placeholderTextColor="#8992a4"
                style={s.searchInput}
                value={query}
              />
            </View>
            <Pressable onPress={() => onChoose("all")} style={s.pickerAll}>
              <Text style={s.pickerAllText}>{allLabel}</Text>
            </Pressable>
            <FlatList
              contentContainerStyle={s.pickerList}
              data={visibleItems}
              keyExtractor={(item) => item.id}
              ListEmptyComponent={
                <Text style={s.empty}>No matching options.</Text>
              }
              renderItem={({ item }) => (
                <Pressable
                  onPress={() => onChoose(item.id)}
                  style={s.pickerItem}
                >
                  <Text numberOfLines={1} style={s.pickerItemText}>
                    {item.label}
                  </Text>
                </Pressable>
              )}
            />
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

function FilterRow({
  label,
  value,
  onPress,
  disabled = false,
}: {
  label: string;
  value: string;
  onPress(): void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[s.filterRow, disabled && s.filterRowDisabled]}
    >
      <View>
        <Text style={[s.filterRowLabel, disabled && s.filterRowDisabledText]}>
          {label}
        </Text>
        <Text
          numberOfLines={1}
          style={[s.filterRowValue, disabled && s.filterRowDisabledText]}
        >
          {value}
        </Text>
      </View>
      <ChevronRight color={disabled ? "#b6bdca" : "#7a8499"} size={20} />
    </Pressable>
  );
}

function assignmentSummary(value: string | undefined, options?: Options) {
  if (!value || value === "all") return "All assignments";
  const [kind, id] = value.split(":");
  if (kind === "trip")
    return options?.trips.find((trip) => trip.id === id)?.label || "Trip";
  return (
    options?.rental_properties.find((property) => property.id === id)?.label ||
    "Rental property"
  );
}

function DateField({
  label,
  value,
  onChange,
  month,
}: {
  label: string;
  value: Date;
  onChange(value: Date): void;
  month?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <View>
      <Label text={label} />
      <Pressable onPress={() => setOpen(true)} style={s.dateField}>
        <CalendarDays color="#4d53b7" size={18} />
        <Text style={s.dateText}>
          {month
            ? value.toLocaleDateString("en-US", {
                month: "long",
                year: "numeric",
              })
            : formatDate(value)}
        </Text>
      </Pressable>
      {open ? (
        <DateTimePicker
          display="default"
          mode="date"
          onChange={(_, date) => {
            setOpen(false);
            if (date) onChange(date);
          }}
          value={value}
        />
      ) : null}
    </View>
  );
}

function ModalHeader({ title, onClose }: { title: string; onClose(): void }) {
  return (
    <View style={s.header}>
      <Text numberOfLines={1} style={s.modalTitle}>
        {title}
      </Text>
      <IconButton onPress={onClose}>
        <X color="#4d53b7" size={22} />
      </IconButton>
    </View>
  );
}
function Label({ text }: { text: string }) {
  return <Text style={s.label}>{text}</Text>;
}
function Chip({
  label,
  active,
  onPress,
  disabled,
}: {
  label: string;
  active: boolean;
  onPress(): void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[s.chip, active && s.chipActive, disabled && s.chipDisabled]}
    >
      <Text style={[s.chipText, active && s.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}
function IconButton({
  children,
  onPress,
}: {
  children: React.ReactNode;
  onPress(): void;
}) {
  return (
    <Pressable hitSlop={6} onPress={onPress} style={s.iconButton}>
      {children}
    </Pressable>
  );
}
function Button({
  label,
  onPress,
  disabled,
  danger,
}: {
  label: string;
  onPress(): void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[s.button, danger && s.danger, disabled && s.disabled]}
    >
      <Text style={[s.buttonText, danger && s.dangerText]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, padding: 18, paddingBottom: 132 },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },
  title: { color: "#182033", fontSize: 23, fontWeight: "700" },
  modalTitle: {
    color: "#182033",
    flex: 1,
    fontSize: 20,
    fontWeight: "700",
    marginRight: 12,
  },
  muted: { color: "#8992a4", fontSize: 11, marginTop: 3 },
  actions: { flexDirection: "row", gap: 7 },
  iconButton: {
    alignItems: "center",
    borderColor: "#d9dfeb",
    borderRadius: 7,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  searchField: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#dfe4ed",
    borderRadius: 7,
    borderWidth: 1,
    flexDirection: "row",
    marginTop: 14,
    minHeight: 46,
    paddingHorizontal: 11,
  },
  searchInput: { color: "#182033", flex: 1, minHeight: 44, paddingLeft: 8 },
  statusChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginVertical: 10,
  },
  inlineChips: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 9 },
  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 9,
  },
  chip: {
    borderColor: "#d9dfeb",
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 9,
    paddingVertical: 7,
  },
  chipActive: { backgroundColor: "#eef0ff", borderColor: "#6268dc" },
  chipDisabled: { opacity: 0.65 },
  chipText: { color: "#657087", fontSize: 11, textTransform: "capitalize" },
  chipTextActive: { color: "#4d53b7", fontWeight: "700" },
  input: {
    backgroundColor: "#fff",
    borderColor: "#dfe4ed",
    borderRadius: 7,
    borderWidth: 1,
    color: "#182033",
    marginTop: 10,
    minHeight: 44,
    paddingHorizontal: 11,
  },
  readOnlyInput: { backgroundColor: "#f0f2f6", color: "#657087" },
  dateField: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#dfe4ed",
    borderRadius: 7,
    borderWidth: 1,
    flexDirection: "row",
    marginTop: 8,
    minHeight: 44,
    paddingHorizontal: 11,
  },
  dateText: { color: "#263047", fontSize: 13, marginLeft: 9 },
  loader: { marginTop: 80 },
  list: { paddingBottom: 16 },
  row: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 7,
    borderWidth: 1,
    flexDirection: "row",
    marginBottom: 7,
    padding: 11,
  },
  rowBody: { flex: 1 },
  merchant: { color: "#263047", fontSize: 13, fontWeight: "700" },
  meta: { color: "#8992a4", fontSize: 10, marginTop: 3 },
  amount: { fontSize: 12, fontWeight: "700", marginLeft: 8 },
  inflow: { color: "#159f72" },
  outflow: { color: "#c54f68" },
  pagination: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },
  button: {
    alignItems: "center",
    backgroundColor: "#6268dc",
    borderRadius: 7,
    justifyContent: "center",
    marginTop: 12,
    minHeight: 44,
    paddingHorizontal: 12,
  },
  buttonText: { color: "#fff", fontSize: 12, fontWeight: "700" },
  disabled: { opacity: 0.4 },
  danger: {
    backgroundColor: "#fff2f4",
    borderColor: "#e49aaa",
    borderWidth: 1,
  },
  dangerText: { color: "#a83f58" },
  error: {
    backgroundColor: "#fff2f4",
    borderRadius: 7,
    marginVertical: 8,
    padding: 10,
  },
  errorText: { color: "#a83f58", fontSize: 12, marginTop: 8 },
  empty: { color: "#8992a4", padding: 30, textAlign: "center" },
  scrim: { backgroundColor: "rgba(20,25,35,.45)", flex: 1 },
  modalSafe: { flex: 1, justifyContent: "flex-end" },
  modal: {
    backgroundColor: "#f7f8fb",
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    maxHeight: "94%",
    padding: 18,
    paddingBottom: 34,
  },
  modalAmount: {
    color: "#263047",
    fontSize: 20,
    fontWeight: "700",
    marginTop: 9,
  },
  label: { color: "#4c566b", fontSize: 12, fontWeight: "700", marginTop: 13 },
  note: { minHeight: 74, paddingTop: 10, textAlignVertical: "top" },
  warning: { color: "#a83f58", fontSize: 12, marginTop: 18 },
  candidate: {
    backgroundColor: "#fff",
    borderColor: "#dfe4ed",
    borderRadius: 7,
    borderWidth: 1,
    marginTop: 7,
    padding: 10,
  },
  filterSheet: {
    backgroundColor: "#f7f8fb",
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    maxHeight: "92%",
    minHeight: "62%",
    paddingTop: 18,
  },
  filterScroll: { flexGrow: 0 },
  filterBody: { paddingHorizontal: 18, paddingBottom: 16 },
  filterFooter: {
    borderTopColor: "#dfe4ed",
    borderTopWidth: 1,
    flexDirection: "row",
    gap: 10,
    padding: 14,
  },
  resetButton: {
    alignItems: "center",
    borderColor: "#6268dc",
    borderRadius: 7,
    borderWidth: 1,
    flex: 1,
    justifyContent: "center",
    minHeight: 44,
  },
  resetButtonText: { color: "#4d53b7", fontSize: 12, fontWeight: "700" },
  applyButton: {
    alignItems: "center",
    backgroundColor: "#6268dc",
    borderRadius: 7,
    flex: 2,
    justifyContent: "center",
    minHeight: 44,
  },
  filterRow: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderBottomColor: "#e1e6ef",
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 66,
    paddingHorizontal: 2,
  },
  filterRowDisabled: { backgroundColor: "#f7f8fb" },
  filterRowDisabledText: { color: "#a4acba" },
  filterRowLabel: { color: "#263047", fontSize: 13, fontWeight: "700" },
  filterRowValue: {
    color: "#7a8499",
    fontSize: 12,
    marginTop: 4,
    maxWidth: 260,
  },
  clearDates: { alignSelf: "flex-start", marginTop: 12, paddingVertical: 7 },
  clearDatesText: { color: "#4d53b7", fontSize: 12, fontWeight: "700" },
  pickerSheet: {
    backgroundColor: "#f7f8fb",
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    flex: 1,
    maxHeight: "94%",
    minHeight: "72%",
    padding: 18,
  },
  assignmentTabs: { flexDirection: "row", gap: 6, marginTop: 13 },
  pickerAll: {
    backgroundColor: "#eef0ff",
    borderColor: "#6268dc",
    borderRadius: 7,
    borderWidth: 1,
    marginTop: 10,
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 12,
  },
  pickerAllText: { color: "#4d53b7", fontSize: 13, fontWeight: "700" },
  pickerList: { paddingBottom: 22, paddingTop: 8 },
  pickerItem: {
    backgroundColor: "#fff",
    borderBottomColor: "#e1e6ef",
    borderBottomWidth: 1,
    justifyContent: "center",
    minHeight: 52,
    paddingHorizontal: 12,
  },
  pickerItemText: { color: "#263047", fontSize: 13 },
});
