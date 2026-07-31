#pragma once

#include <QDialog>

class QPlainTextEdit;

class StatusDialog : public QDialog
{
    Q_OBJECT

public:
    explicit StatusDialog(QWidget *parent = nullptr);

    void showStatus(const QString &title, const QStringList &lines);

protected:
    void keyPressEvent(QKeyEvent *event) override;
    void showEvent(QShowEvent *event) override;

private:
    QPlainTextEdit *m_text = nullptr;
};
