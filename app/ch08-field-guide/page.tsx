import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('ch08-field-guide', Article);
export { metadata };
export default Page;
