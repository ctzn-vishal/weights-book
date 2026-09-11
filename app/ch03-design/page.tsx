import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('ch03-design', Article);
export { metadata };
export default Page;
