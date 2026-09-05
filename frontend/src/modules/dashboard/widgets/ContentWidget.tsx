import { FileImageOutlined } from "@ant-design/icons";
import { Avatar, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { StatusBadge } from "@/design-system";
import { ToneTag } from "@/design-system";
import { ChartFrame } from "@/design-system";
import { Donut } from "../charts/Donut";
import { SERIES_COLORS } from "../charts/theme";
import type { ContentBlock } from "../types";
import { ViewAll, When } from "./shared";

export function ContentWidget({
  content,
  loading,
  error,
  onRetry,
}: {
  content?: ContentBlock;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const navigate = useNavigate();
  const total = content ? Object.values(content.by_status).reduce((n, v) => n + v, 0) : 0;
  const types = content ? Object.entries(content.by_type).sort((a, b) => b[1] - a[1]) : [];
  const summary = content
    ? `${total} items: ${content.by_status.published ?? 0} published, ${content.by_status.draft ?? 0} draft` +
      (types.length ? `; mostly ${types[0][0]}.` : ".")
    : undefined;

  return (
    <ChartFrame
      title="Content"
      extra={<ViewAll to="/content" />}
      summary={summary}
      loading={loading && !content}
      error={error}
      onRetry={onRetry}
      empty={!!content && total === 0}
      emptyTitle="No content yet"
      emptyDescription="Upload images or videos to start building playlists."
      emptyAction={<Link to="/content">Upload content</Link>}
    >
      {content && (
        <>
          <div className="mb-2 flex flex-wrap gap-2">
            {Object.entries(content.by_status).map(([status, count]) => (
              <Link key={status} to={`/content?status=${status}`} className="no-underline">
                <span className="inline-flex items-center gap-1">
                  <StatusBadge status={status} />
                  <Typography.Text strong className="text-[13px]">
                    {count}
                  </Typography.Text>
                </span>
              </Link>
            ))}
          </div>
          <Donut
            height={170}
            centre={total}
            centreLabel="items"
            slices={types.map(([type, count], i) => ({
              key: type,
              label: type.charAt(0).toUpperCase() + type.slice(1),
              value: count,
              color: SERIES_COLORS[i % SERIES_COLORS.length],
            }))}
            onSelect={(type) => navigate(`/content?type=${type}`)}
          />
          {content.recent.length > 0 && (
            <div className="mt-3">
              <Typography.Text strong className="text-[13px]">
                Recently added
              </Typography.Text>
              <ul className="m-0 list-none p-0 divide-y divide-slate-200 dark:divide-slate-700">
                {content.recent.map((a) => (
                  <li key={a.id} className="flex items-center gap-3 py-1.5">
                    <Avatar shape="square" size={32} src={a.thumbnail_url ?? undefined} icon={<FileImageOutlined />} />
                    <div className="min-w-0 flex-1">
                      <Typography.Text ellipsis className="block">
                        {a.name}
                      </Typography.Text>
                      <Typography.Text type="secondary" className="block text-xs">
                        <ToneTag tone="default" className="!me-1">{a.type}</ToneTag>
                        <When iso={a.created_at} />
                      </Typography.Text>
                    </div>
                    <StatusBadge status={a.status} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </ChartFrame>
  );
}
