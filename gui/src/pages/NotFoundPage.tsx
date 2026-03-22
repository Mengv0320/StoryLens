import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 p-8 text-center">
      <h1 className="text-5xl font-bold text-txt-faint">404</h1>
      <p className="text-txt-soft">页面不存在</p>
      <Link to="/" className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:opacity-90 transition-opacity">
        返回首页
      </Link>
    </div>
  );
}
