import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('ch06-clustering', Article);
export { metadata };
export default Page;
