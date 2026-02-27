export default function TableSkeleton({
  cols,
  rows = 8,
}: {
  cols: number;
  rows?: number;
}) {
  const widths = ['55px', '75%', '60%', '50%', '55%', '45%', '70px', '80px', '70px'];
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b last:border-0">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="px-3 py-3">
              <div
                className="h-4 rounded animate-pulse bg-gray-100"
                style={{ width: widths[j] ?? '60%' }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
