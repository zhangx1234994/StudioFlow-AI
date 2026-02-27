import "./globals.css";

export const metadata = {
  title: "AI摄影棚",
  description: "AI摄影棚 - 电商出图出片工作台",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
