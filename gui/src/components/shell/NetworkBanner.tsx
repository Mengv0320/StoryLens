import { useNetworkStatus } from "../../lib/useNetworkStatus";

export default function NetworkBanner() {
  const offline = useNetworkStatus();
  if (!offline) return null;
  return (
    <div className="fixed top-14 inset-x-0 z-50 bg-danger text-white text-center py-2 text-sm shadow-md">
      网络连接异常，正在重试...
    </div>
  );
}
