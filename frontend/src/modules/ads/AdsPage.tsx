import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, DatePicker, Form, Input, InputNumber, Popconfirm, Select, Space, Tabs, TimePicker, Typography, type TableProps } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";
import { PageContainer } from "@/design-system";
import { DataTable } from "@/design-system";

import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface InventoryRow {
  id: string;
  name: string;
  device_id: string | null;
  location_id: string | null;
  slot_type: string;
  operating_hours: { start: string; end: string; days: number[] | null };
  rate_card_ref: string | null;
  active: boolean;
  bookings: number;
}

interface BookingRow {
  id: string;
  inventory_id: string;
  campaign_id: string;
  advertiser_ref: string;
  booked_units: number;
  start_at: string;
  end_at: string;
  status: string;
  links: number;
}

interface InventoryFormValues {
  name: string;
  device_id: string;
  start: Dayjs;
  end: Dayjs;
}

interface BookingFormValues {
  inventory_id: string;
  campaign_id: string;
  advertiser: string;
  units: number;
  start: Dayjs;
  end: Dayjs;
}

/** P3-09/10 Ad Inventory + Bookings. Delivery rides existing campaigns;
 * bookings route through the shared Approvals inbox before confirming. */
export function AdsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("ads.manage");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"inventory" | "bookings">("inventory");
  const [error, setError] = useState<string | null>(null);
  const [invForm] = Form.useForm<InventoryFormValues>();
  const [bookForm] = Form.useForm<BookingFormValues>();

  const inventoryQuery = useQuery({
    queryKey: ["ad-inventory"],
    queryFn: () => api.get<InventoryRow[]>("/ad-inventory"),
    retry: false,
  });
  const bookingsQuery = useQuery({
    queryKey: ["ad-bookings"],
    queryFn: () => api.get<BookingRow[]>("/ad-campaigns"),
    retry: false,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/campaigns?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ad-inventory"] });
    queryClient.invalidateQueries({ queryKey: ["ad-bookings"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createInventory = useMutation({
    mutationFn: (values: InventoryFormValues) =>
      api.post("/ad-inventory", {
        name: values.name,
        device_id: values.device_id || null,
        operating_hours: {
          start: values.start.format("HH:mm"),
          end: values.end.format("HH:mm"),
        },
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      invForm.resetFields();
    },
    onError,
  });

  const createBooking = useMutation({
    mutationFn: (values: BookingFormValues) =>
      api.post("/ad-campaigns", {
        inventory_id: values.inventory_id,
        campaign_id: values.campaign_id,
        advertiser_ref: values.advertiser,
        booked_units: Number(values.units),
        start_at: values.start.toDate().toISOString(),
        end_at: values.end.toDate().toISOString(),
      }),
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const cancelBooking = useMutation({
    mutationFn: (id: string) => api.post(`/ad-campaigns/${id}/cancel`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  if (inventoryQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          inventoryQuery.error instanceof ApiError
            ? inventoryQuery.error.message
            : "Advertising unavailable."
        }
      />
    );

  const inventory = inventoryQuery.data?.data ?? [];
  const bookings = bookingsQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const inventoryName = (id: string) => inventory.find((i) => i.id === id)?.name ?? "—";
  const campaignName = (id: string) => campaigns.find((c) => c.id === id)?.name ?? "—";

  const inventoryColumns: TableProps<InventoryRow>["columns"] = [
    {
      title: "Slot",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    { title: "Type", dataIndex: "slot_type", responsive: ["lg"] },
    {
      title: "Hours",
      render: (_, slot) =>
        `${slot.operating_hours.start}–${slot.operating_hours.end}`,
    },
    { title: "Bookings", dataIndex: "bookings", align: "right", width: 100 },
    {
      title: "Status",
      render: (_, slot) => <StatusBadge status={slot.active ? "active" : "inactive"} />,
    },
  ];

  const bookingColumns: NonNullable<TableProps<BookingRow>["columns"]> = [
    {
      title: "Advertiser",
      dataIndex: "advertiser_ref",
      render: (ref: string) => <Typography.Text strong>{ref}</Typography.Text>,
    },
    { title: "Slot", render: (_, b) => inventoryName(b.inventory_id) },
    {
      title: "Campaign",
      responsive: ["lg"],
      render: (_, b) => campaignName(b.campaign_id),
    },
    {
      title: "Booked plays",
      dataIndex: "booked_units",
      align: "right",
      responsive: ["lg"],
    },
    { title: "Delivered", dataIndex: "links", align: "right", responsive: ["xl"] },
    { title: "Status", render: (_, b) => <StatusBadge status={b.status} /> },
  ];
  if (canManage)
    bookingColumns.push({
      title: "Actions",
      render: (_, b) =>
        (b.status === "pending" || b.status === "confirmed") && (
          <Popconfirm
            title={`Cancel booking for ${b.advertiser_ref}?`}
            okButtonProps={{ danger: true }}
            onConfirm={() => cancelBooking.mutate(b.id)}
          >
            <Button size="small" danger>
              Cancel
            </Button>
          </Popconfirm>
        ),
    });

  const inventoryTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      {canManage && (
        <Card size="small">
          <Form
            form={invForm}
            layout="inline"
            className="gap-y-2"
            initialValues={{
              start: dayjs("09:00", "HH:mm"),
              end: dayjs("21:00", "HH:mm"),
            }}
            onFinish={(values) => {
              setError(null);
              createInventory.mutate(values);
            }}
          >
            <Form.Item
              name="name"
              label="Slot name"
              rules={[{ required: true, message: "Slot name is required." }]}
            >
              <Input className="w-44" />
            </Form.Item>
            <Form.Item
              name="device_id"
              label="Device"
              rules={[{ required: true, message: "Select a device." }]}
            >
              <Select
                className="w-44"
                placeholder="Select…"
                options={devices.map((d) => ({ value: d.id, label: d.name }))}
              />
            </Form.Item>
            <Form.Item
              name="start"
              label="From"
              rules={[{ required: true, message: "Required." }]}
            >
              <TimePicker format="HH:mm" allowClear={false} />
            </Form.Item>
            <Form.Item
              name="end"
              label="To"
              rules={[{ required: true, message: "Required." }]}
            >
              <TimePicker format="HH:mm" allowClear={false} />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlusOutlined />}
                loading={createInventory.isPending}
              >
                Add slot
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}
      <DataTable<InventoryRow>
        rowKey="id"
        columns={inventoryColumns}
        dataSource={inventory}
        loading={inventoryQuery.isLoading}
        emptyTitle="No inventory yet"
      />
    </Space>
  );

  const bookingsTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      {canManage && (
        <Card size="small">
          <Form
            form={bookForm}
            layout="inline"
            className="gap-y-2"
            initialValues={{ units: 100 }}
            onFinish={(values) => {
              setError(null);
              createBooking.mutate(values);
            }}
          >
            <Form.Item
              name="inventory_id"
              label="Slot"
              rules={[{ required: true, message: "Select a slot." }]}
            >
              <Select
                className="w-44"
                placeholder="Select…"
                options={inventory.map((i) => ({ value: i.id, label: i.name }))}
              />
            </Form.Item>
            <Form.Item
              name="campaign_id"
              label="Campaign"
              rules={[{ required: true, message: "Select a campaign." }]}
            >
              <Select
                className="w-44"
                placeholder="Select…"
                options={campaigns.map((c) => ({ value: c.id, label: c.name }))}
              />
            </Form.Item>
            <Form.Item
              name="advertiser"
              label="Advertiser"
              rules={[{ required: true, message: "Advertiser is required." }]}
            >
              <Input className="w-44" />
            </Form.Item>
            <Form.Item name="units" label="Units (plays)">
              <InputNumber min={1} className="w-28" />
            </Form.Item>
            <Form.Item
              name="start"
              label="From"
              rules={[{ required: true, message: "Required." }]}
            >
              <DatePicker showTime format="YYYY-MM-DD HH:mm" />
            </Form.Item>
            <Form.Item
              name="end"
              label="To"
              rules={[{ required: true, message: "Required." }]}
            >
              <DatePicker showTime format="YYYY-MM-DD HH:mm" />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlusOutlined />}
                loading={createBooking.isPending}
              >
                Book
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}
      <Typography.Text type="secondary" className="text-xs">
        New bookings await approval in the Approvals inbox before confirming.
      </Typography.Text>
      <DataTable<BookingRow>
        rowKey="id"
        columns={bookingColumns}
        dataSource={bookings}
        loading={bookingsQuery.isLoading}
        emptyTitle="No bookings yet"
      />
    </Space>
  );

  return (
    <PageContainer
        title="Advertising"
        description="Sell screen time: inventory slots, bookings against existing campaigns, and billing-ready proof-of-play reconciliation (see Reports → Ads)."
      >
      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as "inventory" | "bookings")}
        items={[
          { key: "inventory", label: "Inventory", children: inventoryTab },
          { key: "bookings", label: "Bookings", children: bookingsTab },
        ]}
      />
      {error && (
        <Alert type="error" showIcon role="alert" message={error} className="mt-4" />
      )}
    </PageContainer>
  );
}
