'use client';

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import { explainText, ExplainTextResponse } from '@/lib/api'; // 引入新增加的函数

// 设置 worker 路径
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  pageNumber: number;
  /** 跨页条文结束页（C 轮 16.36）：与 pageNumber 构成渲染区间，跨页条文需同时看到两页 */
  endPage?: number;
  onClose: () => void;
}

export default function PdfViewer({ pageNumber, endPage, onClose }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // 选词解释相关状态
  const [selectedText, setSelectedText] = useState<string>('');
  const [explanation, setExplanation] = useState<ExplainTextResponse | null>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });
  

  const safePageNumber = Math.max(1, Math.min(pageNumber, numPages || 999));
  // 跨页区间：endPage 缺省或小于起始页时退化为单页渲染
  const safeEndPage = Math.max(safePageNumber, Math.min(endPage ?? pageNumber, numPages || 999));
  const pageLabel = safeEndPage > safePageNumber
    ? `第 ${safePageNumber}-${safeEndPage} 页`
    : `第 ${safePageNumber} 页`;

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  // 监听鼠标松开事件，处理选词
  useEffect(() => {
    const handleMouseUp = async (e: MouseEvent) => {
      const selection = window.getSelection();
      const text = selection?.toString().trim();

      if (text && text.length > 2) {
        setSelectedText(text);
        setPopupPosition({ x: e.clientX, y: e.clientY });
        setLoadingExplanation(true);

        try {
          // 调用 api.ts 中的统一接口
          const data = await explainText({ question: text });
          setExplanation(data);
        } catch (err) {
          setError('获取解释失败，请检查服务连接。');
        } finally {
          setLoadingExplanation(false);
        }
      } else {
        setSelectedText('');
      }
    };

    document.addEventListener('mouseup', handleMouseUp);
    return () => document.removeEventListener('mouseup', handleMouseUp);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl overflow-hidden dark:bg-zinc-900">
        <div className="flex items-center justify-between p-4 border-b dark:border-zinc-800">
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-50">古籍原文预览 - {pageLabel}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-50">✕</button>
        </div>
        
        <div className="overflow-auto max-h-[80vh] p-4 bg-zinc-100 dark:bg-zinc-950 flex justify-center relative">
          <Document
            file="/guilinguben.pdf"
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={(err) => setError('PDF 加载失败')}
            className="shadow-lg"
          >
            {Array.from({ length: safeEndPage - safePageNumber + 1 }, (_, i) => (
              <Page
                key={safePageNumber + i}
                pageNumber={safePageNumber + i}
                renderTextLayer={true}
                renderAnnotationLayer={false}
                width={800}
              />
            ))}
          </Document>

          {/* 选词解释弹窗 */}
          {selectedText && (
            <div 
              className="absolute z-[100] w-72 bg-white dark:bg-zinc-800 rounded-lg shadow-xl border border-emerald-200 dark:border-emerald-800 p-3 text-sm animate-in fade-in zoom-in duration-200"
              style={{ 
                left: Math.min(popupPosition.x, window.innerWidth - 320), 
                top: Math.min(popupPosition.y + 20, window.innerHeight - 200) 
              }}
            >
              <div className="font-mono text-xs text-emerald-600 mb-1 truncate">"{selectedText}"</div>
              {loadingExplanation ? (
                <div className="text-zinc-500">正在分析...</div>
              ) : (
                <div className="text-zinc-700 dark:text-zinc-300">{explanation?.answer}</div>
              )}
              <button 
                onClick={() => setSelectedText('')} 
                className="absolute top-1 right-1 text-zinc-400 hover:text-red-500"
              >✕</button>
            </div>
          )}
        </div>

        {error && <div className="p-4 text-center text-red-500">{error}</div>}
      </div>
    </div>
  );
}
